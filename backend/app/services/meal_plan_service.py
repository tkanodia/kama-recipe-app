"""Meal plan service — LLM-powered meal plan generation persisted as Artifact."""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_chat
from app.models.tables import Artifact
from app.repositories import artifact_repo, canonical_recipe_repo
from app.services.search_service import search_recipes

log = structlog.get_logger()

SYSTEM_PROMPT = (
    "You are Kama, a meal planning assistant. Create a meal plan using ONLY "
    "the recipes provided below. Return JSON with 'days' array, each with "
    "'day' (number), 'label' (e.g. 'Monday'), and 'slots' array. Each slot "
    "has 'meal' (e.g. 'Breakfast', 'Lunch', 'Dinner'), 'recipeId' (from "
    "provided recipes), 'recipeTitle', and optional 'notes'."
)


async def generate_meal_plan(
    db: AsyncSession,
    *,
    instructions: str | None = None,
    recipe_ids: list[str] | None = None,
    days: int = 7,
    meals_per_day: int = 3,
    title: str | None = None,
    user_id: str,
) -> Artifact:
    log.info("meal_plan_generate_start", user_id=user_id, days=days, meals_per_day=meals_per_day)
    recipes_data = await _gather_recipes(db, user_id, recipe_ids, instructions)

    recipe_block = _format_recipes_for_prompt(recipes_data)
    user_prompt = _build_user_prompt(
        recipe_block=recipe_block,
        days=days,
        meals_per_day=meals_per_day,
        instructions=instructions,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        llm_response = await llm_chat(messages, json_mode=True, max_tokens=4096, temperature=0.3)
        content = _parse_and_validate(llm_response.text, recipes_data)
    except Exception:
        log.error("meal_plan_generation_failed", user_id=user_id, exc_info=True)
        raise

    plan_title = title or f"Meal Plan — {days} days"
    source_ids = [r["id"] for r in recipes_data]

    artifact = await artifact_repo.create(
        db,
        user_id=user_id,
        artifact_type="meal_plan",
        title=plan_title,
        content=content,
        source_recipe_ids=source_ids,
    )
    log.info("meal_plan_generate_done", artifact_id=artifact.id, recipe_count=len(source_ids))
    return artifact


async def _gather_recipes(
    db: AsyncSession,
    user_id: str,
    recipe_ids: list[str] | None,
    instructions: str | None,
) -> list[dict[str, Any]]:
    recipes_data: list[dict[str, Any]] = []

    if recipe_ids:
        for rid in recipe_ids:
            recipe = await canonical_recipe_repo.get_by_id(db, rid)
            if recipe and recipe.user_id == user_id:
                recipes_data.append(_recipe_to_summary(recipe))
    else:
        query = instructions or ""
        search_results = await search_recipes(
            query=query if query else None,
            filters=None,
            user_id=user_id,
            limit=20,
            db=db,
        )
        for sr in search_results.items:
            recipes_data.append(_recipe_to_summary(sr.recipe))

    return recipes_data


def _recipe_to_summary(recipe: Any) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "prepTimeMinutes": recipe.prep_time_minutes,
        "cookTimeMinutes": recipe.cook_time_minutes,
        "servings": recipe.servings,
        "tags": [
            t.get("name", "") for t in (recipe.recipe_tags or []) if isinstance(t, dict)
        ],
    }


def _format_recipes_for_prompt(recipes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for r in recipes:
        parts = [f"- {r['title']} (id: {r['id']})"]
        if r.get("prepTimeMinutes"):
            parts.append(f"  prep: {r['prepTimeMinutes']}min")
        if r.get("cookTimeMinutes"):
            parts.append(f"  cook: {r['cookTimeMinutes']}min")
        if r.get("servings"):
            parts.append(f"  servings: {r['servings']}")
        if r.get("tags"):
            parts.append(f"  tags: {', '.join(r['tags'])}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _build_user_prompt(
    recipe_block: str,
    days: int,
    meals_per_day: int,
    instructions: str | None,
) -> str:
    meal_labels = ["Breakfast", "Lunch", "Dinner", "Snack"][:meals_per_day]
    parts = [
        f"Create a {days}-day meal plan with {meals_per_day} meals per day "
        f"({', '.join(meal_labels)}).",
        "",
        "Available recipes:",
        recipe_block,
    ]
    if instructions:
        parts.extend(["", f"Additional instructions: {instructions}"])
    parts.extend([
        "",
        "Return valid JSON with the structure described in the system prompt. "
        "Use only the recipe IDs listed above.",
    ])
    return "\n".join(parts)


def _parse_and_validate(
    raw_text: str,
    recipes_data: list[dict[str, Any]],
) -> dict[str, Any]:
    content = json.loads(raw_text)

    if "days" not in content or not isinstance(content["days"], list):
        raise ValueError("LLM response missing 'days' array")

    valid_ids = {r["id"] for r in recipes_data}

    for day in content["days"]:
        if "slots" not in day or not isinstance(day["slots"], list):
            raise ValueError(f"Day {day.get('day')} missing 'slots' array")
        for slot in day["slots"]:
            rid = slot.get("recipeId")
            if rid and rid not in valid_ids:
                log.warning("meal_plan_invalid_recipe_id", recipe_id=rid)
                slot["recipeId"] = None
                slot["notes"] = (slot.get("notes") or "") + " [recipe not found]"

    return content
