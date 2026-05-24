"""Ask service — retrieval-augmented generation for recipe questions."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_chat, llm_chat_stream
from app.models.tables import AskMessage, CanonicalRecipe
from app.repositories import canonical_recipe_repo
from app.services import search_service

log = structlog.get_logger()

_CORPUS_SYSTEM_PROMPT = (
    "You are Kama, a recipe assistant. Answer questions using ONLY the recipe data "
    "provided below. ALWAYS cite ALL relevant recipes — if multiple recipes match the "
    "user's question, include all of them (aim for 2-5 when possible). Compare and "
    "contrast options when appropriate. Cite recipes by their ID. Do not use external "
    "knowledge. If you can't answer from the provided recipes, say so honestly. Return "
    "JSON with 'content' (your answer) and 'citedRecipeIds' (array of ALL recipe IDs "
    "you referenced — include every recipe that is relevant to the answer)."
)

_CHEF_SYSTEM_PROMPT_TEMPLATE = (
    "You are an expert chef assistant for the recipe '{title}'. Answer cooking questions "
    "about this specific recipe using the recipe details below. Provide practical tips, "
    "substitutions, and technique advice. Return JSON with 'content' (your answer) and "
    "'citedRecipeIds' (array containing this recipe's ID if you reference it)."
)

_STREAM_CORPUS_PROMPT = (
    "You are Kama, a recipe assistant. Answer questions using ONLY the recipe data "
    "provided below. ALWAYS cite ALL relevant recipes — if multiple recipes match the "
    "user's question, include all of them (aim for 2-5 when possible). Compare and "
    "contrast options when appropriate. When referencing a recipe, include its ID in "
    "square brackets like [rec_xxxxx] inline. Do not use external knowledge. "
    "If you can't answer from the provided recipes, say so honestly."
)

_STREAM_CHEF_PROMPT_TEMPLATE = (
    "You are an expert chef assistant for the recipe '{title}'. Answer cooking questions "
    "about this specific recipe using the recipe details below. Provide practical tips, "
    "substitutions, and technique advice. When referencing the recipe, include its ID "
    "in square brackets like [rec_xxxxx] inline."
)


def _augment_query_with_context(question: str, session_messages: list[AskMessage]) -> str:
    """Augment a follow-up question with context from prior conversation turns."""
    if not session_messages:
        return question
    recent_user_msgs = [
        m.content for m in session_messages[-4:]
        if m.role == "user" and m.content
    ]
    if not recent_user_msgs:
        return question
    context = "; ".join(recent_user_msgs[-2:])
    return f"{question} (context: {context})"


async def retrieve_for_ask(
    question: str,
    session_messages: list[AskMessage],
    user_id: str,
    recipe_id: str | None = None,
    db: AsyncSession | None = None,
) -> list[CanonicalRecipe]:
    log.info("ask_retrieve_start", user_id=user_id, recipe_id=recipe_id, question_len=len(question))

    if recipe_id and db:
        recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
        if recipe:
            log.info("ask_retrieve_done", source="single_recipe", count=1)
            return [recipe]
        log.info("ask_retrieve_done", source="single_recipe", count=0)
        return []

    augmented_query = _augment_query_with_context(question, session_messages)

    try:
        results = await search_service.search_recipes(
            query=augmented_query,
            filters=None,
            user_id=user_id,
            limit=10,
            db=db,
        )
        recipes = [sr.recipe for sr in results.items]
        log.info("ask_retrieve_done", source="search", count=len(recipes))
        return recipes
    except Exception:
        log.error("ask_retrieval_failed", question=question, exc_info=True)
        return []


def _format_recipe_context(recipes: list[CanonicalRecipe]) -> str:
    parts: list[str] = []
    for r in recipes:
        ingredients_text = ", ".join(
            i.get("text", "") if isinstance(i, dict) else str(i)
            for i in (r.ingredients or [])
        )
        steps_text = " | ".join(
            s.get("text", "") if isinstance(s, dict) else str(s)
            for s in (r.steps or [])
        )
        parts.append(
            f"[{r.id}] {r.title}\n"
            f"  Description: {r.description or 'N/A'}\n"
            f"  Ingredients: {ingredients_text}\n"
            f"  Steps: {steps_text}\n"
            f"  Prep: {r.prep_time_minutes or 'N/A'}min | Cook: {r.cook_time_minutes or 'N/A'}min | "
            f"Servings: {r.servings or 'N/A'}"
        )
    return "\n\n".join(parts)


async def generate_answer(
    question: str,
    retrieved_recipes: list[CanonicalRecipe],
    session_messages: list[AskMessage],
    recipe_id: str | None = None,
) -> dict:
    log.info("ask_generate_start", recipe_id=recipe_id, recipe_count=len(retrieved_recipes))
    try:
        retrieved_ids = {r.id for r in retrieved_recipes}

        if recipe_id and retrieved_recipes:
            system_prompt = _CHEF_SYSTEM_PROMPT_TEMPLATE.format(
                title=retrieved_recipes[0].title,
            )
        else:
            system_prompt = _CORPUS_SYSTEM_PROMPT

        recipe_context = _format_recipe_context(retrieved_recipes)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        if recipe_context:
            messages.append({
                "role": "system",
                "content": f"Recipe data:\n\n{recipe_context}",
            })

        for msg in session_messages:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": question})

        response = await llm_chat(messages, json_mode=True, temperature=0.3)

        parsed = json.loads(response.text)
        content = parsed.get("content", response.text)
        cited_ids = parsed.get("citedRecipeIds", [])

        validated_cited = [rid for rid in cited_ids if rid in retrieved_ids]

        log.info("ask_generate_done", cited_count=len(validated_cited))
        return {"content": content, "citedRecipeIds": validated_cited}

    except Exception:
        log.error("ask_generate_failed", question=question, exc_info=True)
        return {
            "content": "I'm sorry, I couldn't generate an answer right now. Please try again.",
            "citedRecipeIds": [],
        }


_REC_ID_PATTERN = re.compile(r"\[rec_[a-z0-9]+\]")


def extract_cited_ids(text: str, valid_ids: set[str]) -> list[str]:
    """Extract [rec_xxx] IDs from streamed text and validate against retrieved set."""
    found = _REC_ID_PATTERN.findall(text)
    cited = []
    for match in found:
        rid = match[1:-1]  # strip brackets
        if rid in valid_ids and rid not in cited:
            cited.append(rid)
    return cited


async def generate_answer_stream(
    question: str,
    retrieved_recipes: list[CanonicalRecipe],
    session_messages: list[AskMessage],
    recipe_id: str | None = None,
) -> AsyncIterator[str]:
    """Stream answer tokens via SSE. Yields text chunks as they arrive."""
    log.info("ask_generate_stream_start", recipe_id=recipe_id, recipe_count=len(retrieved_recipes))
    try:
        if recipe_id and retrieved_recipes:
            system_prompt = _STREAM_CHEF_PROMPT_TEMPLATE.format(
                title=retrieved_recipes[0].title,
            )
        else:
            system_prompt = _STREAM_CORPUS_PROMPT

        recipe_context = _format_recipe_context(retrieved_recipes)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        if recipe_context:
            messages.append({
                "role": "system",
                "content": f"Recipe data:\n\n{recipe_context}",
            })

        for msg in session_messages:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": question})

        async for chunk in llm_chat_stream(messages, temperature=0.3):
            yield chunk

    except Exception:
        log.error("ask_generate_stream_failed", question=question, exc_info=True)
        yield "I'm sorry, I couldn't generate an answer right now. Please try again."
