"""Query parser service — LLM-assisted decomposition of natural language search queries."""

from __future__ import annotations

import json
from typing import Literal

import structlog
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import llm_breaker
from app.core.llm import llm_chat

log = structlog.get_logger()


class StructuredFilters(BaseModel):
    tag_names: list[str] = Field(default_factory=list, alias="tagNames")
    ingredient_names: list[str] = Field(default_factory=list, alias="ingredientNames")
    max_cook_time_minutes: int | None = Field(default=None, alias="maxCookTimeMinutes")
    max_prep_time_minutes: int | None = Field(default=None, alias="maxPrepTimeMinutes")
    min_servings: int | None = Field(default=None, alias="minServings")
    max_servings: int | None = Field(default=None, alias="maxServings")
    model_config = {"populate_by_name": True}


class ParsedQuery(BaseModel):
    structured_filters: StructuredFilters = Field(default_factory=StructuredFilters, alias="structuredFilters")
    semantic_query: str = Field(default="", alias="semanticQuery")
    query_intent: Literal["search", "ask", "ambiguous"] = Field(default="search", alias="queryIntent")
    tag_ids: list[str] = Field(default_factory=list, alias="tagIds")
    ingredient_ids: list[str] = Field(default_factory=list, alias="ingredientIds")
    model_config = {"populate_by_name": True}


_SYSTEM_PROMPT = """You are a recipe search query parser. Given a user's search query, decompose it into structured components.

Return a JSON object with these fields:
- "semanticQuery": The core semantic meaning to search for (the part that should be matched via embeddings). Remove filter-like phrases.
- "queryIntent": One of "search" (looking for recipes), "ask" (asking a question about cooking), or "ambiguous".
- "tagNames": Array of tag/category names mentioned (e.g. "Italian", "vegan", "dessert").
- "ingredientNames": Array of specific ingredient names mentioned (e.g. "chicken", "garlic", "pasta").
- "maxCookTimeMinutes": Integer if the user specifies a cook time constraint, else null.
- "maxPrepTimeMinutes": Integer if the user specifies a prep time constraint, else null.
- "minServings": Integer if the user specifies minimum servings, else null.
- "maxServings": Integer if the user specifies maximum servings, else null.

Examples:
- "quick chicken pasta under 30 minutes" -> {"semanticQuery": "chicken pasta", "queryIntent": "search", "tagNames": [], "ingredientNames": ["chicken", "pasta"], "maxCookTimeMinutes": 30, "maxPrepTimeMinutes": null, "minServings": null, "maxServings": null}
- "vegan desserts" -> {"semanticQuery": "desserts", "queryIntent": "search", "tagNames": ["vegan"], "ingredientNames": [], "maxCookTimeMinutes": null, "maxPrepTimeMinutes": null, "minServings": null, "maxServings": null}
- "how do I make a roux?" -> {"semanticQuery": "how to make a roux", "queryIntent": "ask", "tagNames": [], "ingredientNames": [], "maxCookTimeMinutes": null, "maxPrepTimeMinutes": null, "minServings": null, "maxServings": null}

Respond with valid JSON only."""


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5), reraise=True)
async def _llm_parse(raw_query: str) -> dict:
    response = await llm_chat(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_query},
        ],
        max_tokens=512,
        temperature=0.0,
        json_mode=True,
    )
    return json.loads(response.text)


async def parse_query(raw_query: str, user_id: str) -> ParsedQuery:
    """Parse a raw search query into structured components with resolved DB IDs."""
    if not raw_query or len(raw_query.strip()) < 2:
        return ParsedQuery(semanticQuery=raw_query.strip(), queryIntent="search")

    try:
        parsed = await _llm_parse(raw_query)
    except Exception:
        log.warning("query_parse_llm_failed", query=raw_query, exc_info=True)
        return ParsedQuery(semanticQuery=raw_query.strip(), queryIntent="search")

    filters = StructuredFilters(
        tagNames=parsed.get("tagNames", []),
        ingredientNames=parsed.get("ingredientNames", []),
        maxCookTimeMinutes=parsed.get("maxCookTimeMinutes"),
        maxPrepTimeMinutes=parsed.get("maxPrepTimeMinutes"),
        minServings=parsed.get("minServings"),
        maxServings=parsed.get("maxServings"),
    )

    tag_ids = await _resolve_tag_ids(filters.tag_names)
    ingredient_ids = await _resolve_ingredient_ids(filters.ingredient_names)

    return ParsedQuery(
        structuredFilters=filters,
        semanticQuery=parsed.get("semanticQuery", raw_query.strip()),
        queryIntent=parsed.get("queryIntent", "search"),
        tagIds=tag_ids,
        ingredientIds=ingredient_ids,
    )


async def _resolve_tag_ids(tag_names: list[str]) -> list[str]:
    """Look up tag names in the DB and return matching IDs."""
    if not tag_names:
        return []

    from app.core.database import SessionLocal
    from app.repositories import tag_repo

    ids: list[str] = []
    async with SessionLocal() as session:
        for name in tag_names:
            tag = await tag_repo.find_by_name_and_domain(session, name, "recipe")
            if tag:
                ids.append(tag.id)
    return ids


async def _resolve_ingredient_ids(ingredient_names: list[str]) -> list[str]:
    """Look up ingredient names in the DB and return matching IDs."""
    if not ingredient_names:
        return []

    from app.core.database import SessionLocal
    from app.repositories import ingredient_repo

    ids: list[str] = []
    async with SessionLocal() as session:
        for name in ingredient_names:
            ing = await ingredient_repo.find_by_name(session, name)
            if ing:
                ids.append(ing.id)
    return ids
