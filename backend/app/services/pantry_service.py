"""Pantry service — add/remove pantry items, text parsing, recipe feasibility."""

from __future__ import annotations

import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import canonical_recipe_repo, ingredient_repo, pantry_repo

log = structlog.get_logger()


async def add_pantry_items(
    db: AsyncSession,
    ingredient_ids: list[str],
    user_id: str,
) -> dict[str, Any]:
    log.info("pantry_add_start", user_id=user_id, count=len(ingredient_ids))
    existing_ids = await pantry_repo.get_ingredient_ids_for_user(db, user_id)
    already_in_pantry = [iid for iid in ingredient_ids if iid in existing_ids]
    to_add = [iid for iid in ingredient_ids if iid not in existing_ids]

    added_rows = await pantry_repo.add_items(db, user_id, to_add)
    log.info("pantry_add_done", added=len(added_rows), skipped=len(already_in_pantry))
    return {
        "added": [
            {"pantryItemId": r.id, "ingredientId": r.ingredient_id}
            for r in added_rows
        ],
        "alreadyInPantry": already_in_pantry,
    }


async def add_from_text(
    db: AsyncSession,
    text: str,
    user_id: str,
) -> dict[str, Any]:
    log.info("pantry_add_from_text_start", user_id=user_id, text_len=len(text))
    tokens = [t.strip() for t in re.split(r"[,\n]+", text) if t.strip()]

    added: list[dict[str, str]] = []
    not_found: list[str] = []
    suggestions: list[dict[str, Any]] = []

    for token in tokens:
        ing = await ingredient_repo.find_by_name(db, token)
        if ing:
            result = await add_pantry_items(db, [ing.id], user_id)
            if result["added"]:
                added.append({"name": ing.name, "ingredientId": ing.id})
            continue

        search_results = await ingredient_repo.search(db, token, limit=3)
        alias_match = next(
            (r for r in search_results if r["matchConfidence"] == "alias"),
            None,
        )
        exact_match = next(
            (r for r in search_results if r["matchConfidence"] == "exact"),
            None,
        )

        if exact_match:
            result = await add_pantry_items(db, [exact_match["id"]], user_id)
            if result["added"]:
                added.append({"name": exact_match["name"], "ingredientId": exact_match["id"]})
        elif alias_match:
            result = await add_pantry_items(db, [alias_match["id"]], user_id)
            if result["added"]:
                added.append({"name": alias_match["name"], "ingredientId": alias_match["id"]})
        elif search_results:
            suggestions.append({
                "query": token,
                "candidates": [
                    {"id": r["id"], "name": r["name"]} for r in search_results
                ],
            })
        else:
            not_found.append(token)

    log.info(
        "pantry_add_from_text_done",
        added=len(added), not_found=len(not_found), suggestions=len(suggestions),
    )
    return {"added": added, "notFound": not_found, "suggestions": suggestions}


async def remove_pantry_items(
    db: AsyncSession,
    pantry_item_ids: list[str],
    user_id: str,
) -> None:
    await pantry_repo.remove_items(db, pantry_item_ids, user_id)


async def check_feasibility(
    db: AsyncSession,
    user_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    log.info("pantry_feasibility_start", user_id=user_id)
    pantry_ingredient_ids = await pantry_repo.get_ingredient_ids_for_user(db, user_id)
    recipes = await canonical_recipe_repo.list_by_user(db, user_id, limit=limit)

    fully_feasible: list[dict] = []
    partially_feasible: list[dict] = []
    not_feasible: list[dict] = []

    for recipe in recipes:
        recipe_ingredients = recipe.ingredients or []
        if not recipe_ingredients:
            continue

        ingredient_ids_in_recipe: set[str] = set()
        ingredient_names: dict[str, str] = {}

        for ing in recipe_ingredients:
            iid = ing.get("ingredientId") or ing.get("id")
            name = (
                ing.get("text", "")
                or (ing.get("mappedIngredient") or {}).get("name", "")
                or ""
            )
            if iid:
                ingredient_ids_in_recipe.add(iid)
                ingredient_names[iid] = name

        total = len(ingredient_ids_in_recipe)
        if total == 0:
            continue

        matched_ids = [iid for iid in ingredient_ids_in_recipe if iid in pantry_ingredient_ids]
        missing_ids = [iid for iid in ingredient_ids_in_recipe if iid not in pantry_ingredient_ids]
        score = len(matched_ids) / total

        entry = {
            "recipeId": recipe.id,
            "recipeTitle": recipe.title,
            "feasibilityScore": round(score, 3),
            "totalIngredients": total,
            "matchedIngredients": len(matched_ids),
            "missingIngredients": [ingredient_names.get(iid, iid) for iid in missing_ids],
        }

        if score == 1.0:
            fully_feasible.append(entry)
        elif score >= 0.5:
            partially_feasible.append(entry)
        else:
            not_feasible.append(entry)

    fully_feasible.sort(key=lambda x: x["feasibilityScore"], reverse=True)
    partially_feasible.sort(key=lambda x: x["feasibilityScore"], reverse=True)
    not_feasible.sort(key=lambda x: x["feasibilityScore"], reverse=True)

    log.info(
        "pantry_feasibility_done",
        fully=len(fully_feasible),
        partial=len(partially_feasible),
        none=len(not_feasible),
    )
    return {
        "fullyFeasible": fully_feasible,
        "partiallyFeasible": partially_feasible,
        "notFeasible": not_feasible,
    }
