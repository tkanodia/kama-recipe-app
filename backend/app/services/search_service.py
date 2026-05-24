"""Search service — end-to-end hybrid search orchestration."""

from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import models as qdrant_models
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import CanonicalRecipe
from app.services.query_parser_service import ParsedQuery, parse_query

log = structlog.get_logger()


class SearchResult:
    def __init__(
        self,
        recipe: CanonicalRecipe,
        relevance_score: float,
        match_reasons: list[str],
    ):
        self.recipe = recipe
        self.relevance_score = relevance_score
        self.match_reasons = match_reasons


class SearchResults:
    def __init__(
        self,
        items: list[SearchResult],
        parsed_query: ParsedQuery,
        next_cursor: int | None,
        has_more: bool,
        search_quality_reduced: bool = False,
    ):
        self.items = items
        self.parsed_query = parsed_query
        self.next_cursor = next_cursor
        self.has_more = has_more
        self.search_quality_reduced = search_quality_reduced


async def search_recipes(
    query: str | None,
    filters: dict[str, Any] | None,
    user_id: str,
    limit: int = 20,
    cursor: int = 0,
    db: AsyncSession | None = None,
) -> SearchResults:
    """Full hybrid search: parse query -> build vectors -> search Qdrant -> hydrate from Postgres."""
    from app.core.database import SessionLocal

    parsed = ParsedQuery(semanticQuery=query or "", queryIntent="search")
    if query:
        try:
            parsed = await parse_query(query, user_id)
        except Exception:
            log.warning("search_query_parse_failed", query=query, exc_info=True)
            parsed = ParsedQuery(semanticQuery=query, queryIntent="search")

    merged_tag_ids = list(parsed.tag_ids)
    merged_ingredient_ids = list(parsed.ingredient_ids)
    max_cook_time = parsed.structured_filters.max_cook_time_minutes
    max_prep_time = parsed.structured_filters.max_prep_time_minutes
    min_servings = parsed.structured_filters.min_servings
    max_servings = parsed.structured_filters.max_servings

    if filters:
        if filters.get("tagIds"):
            for tid in filters["tagIds"]:
                if tid not in merged_tag_ids:
                    merged_tag_ids.append(tid)
        if filters.get("ingredientIds"):
            for iid in filters["ingredientIds"]:
                if iid not in merged_ingredient_ids:
                    merged_ingredient_ids.append(iid)
        if filters.get("maxCookTimeMinutes") is not None:
            max_cook_time = filters["maxCookTimeMinutes"]
        if filters.get("maxPrepTimeMinutes") is not None:
            max_prep_time = filters["maxPrepTimeMinutes"]
        if filters.get("minServings") is not None:
            min_servings = filters["minServings"]
        if filters.get("maxServings") is not None:
            max_servings = filters["maxServings"]

    payload_filter = _build_qdrant_filter(
        user_id=user_id,
        tag_ids=merged_tag_ids,
        ingredient_ids=merged_ingredient_ids,
        max_cook_time=max_cook_time,
        max_prep_time=max_prep_time,
        min_servings=min_servings,
        max_servings=max_servings,
    )

    try:
        hits = await _qdrant_search(
            semantic_query=parsed.semantic_query,
            payload_filter=payload_filter,
            limit=limit + 1,
            offset=cursor,
        )
        search_quality_reduced = False
    except Exception:
        log.warning("qdrant_search_unavailable_falling_back", exc_info=True)
        hits = await _postgres_fallback(
            query=parsed.semantic_query,
            user_id=user_id,
            limit=limit + 1,
            offset=cursor,
        )
        search_quality_reduced = True

    has_more = len(hits) > limit
    trimmed = hits[:limit]

    own_session = db is None
    session = db
    if own_session:
        session = SessionLocal()

    try:
        results = await _hydrate_results(session, trimmed, parsed)
        next_cursor_val = (cursor + limit) if has_more else None

        return SearchResults(
            items=results,
            parsed_query=parsed,
            next_cursor=next_cursor_val,
            has_more=has_more,
            search_quality_reduced=search_quality_reduced,
        )
    finally:
        if own_session and session:
            await session.close()


async def _qdrant_search(
    semantic_query: str,
    payload_filter: qdrant_models.Filter,
    limit: int,
    offset: int,
) -> list[tuple[str, float]]:
    """Search Qdrant with hybrid vectors or filter-only."""
    from app.services.embedding_service import generate_dense_embedding, generate_sparse_vector
    from app.services.qdrant_client_service import filter_only_search, hybrid_search

    if not semantic_query or not semantic_query.strip():
        return await filter_only_search(payload_filter, limit=limit, offset=offset)

    dense_vector = await generate_dense_embedding(semantic_query)
    sparse_vector = generate_sparse_vector(semantic_query)
    return await hybrid_search(dense_vector, sparse_vector, payload_filter, limit=limit, offset=offset)


async def _postgres_fallback(
    query: str,
    user_id: str,
    limit: int,
    offset: int,
) -> list[tuple[str, float]]:
    """Fallback to Postgres ILIKE when Qdrant is unavailable."""
    from app.core.database import SessionLocal
    from app.repositories import canonical_recipe_repo

    async with SessionLocal() as session:
        recipes = await canonical_recipe_repo.list_by_user(
            session, user_id, search=query if query else None, limit=limit,
        )
        return [(r.id, 1.0) for r in recipes]


async def _hydrate_results(
    session: AsyncSession,
    hits: list[tuple[str, float]],
    parsed: ParsedQuery,
) -> list[SearchResult]:
    """Hydrate recipe IDs from Qdrant into full SearchResult objects."""
    from app.repositories import canonical_recipe_repo

    results: list[SearchResult] = []
    for recipe_id, score in hits:
        if not recipe_id:
            continue
        recipe = await canonical_recipe_repo.get_by_id(session, recipe_id)
        if recipe is None:
            continue

        match_reasons = _compose_match_reasons(recipe, parsed)
        results.append(SearchResult(
            recipe=recipe,
            relevance_score=score,
            match_reasons=match_reasons,
        ))

    return results


def _compose_match_reasons(recipe: CanonicalRecipe, parsed: ParsedQuery) -> list[str]:
    """Generate human-readable match reasons for a search result."""
    reasons: list[str] = []

    if parsed.semantic_query:
        reasons.append(f"Matches: {parsed.semantic_query}")

    recipe_tag_ids = {t.get("id", "") for t in (recipe.recipe_tags or []) if isinstance(t, dict)}
    for tid in parsed.tag_ids:
        if tid in recipe_tag_ids:
            tag_name = next(
                (t.get("name", "") for t in (recipe.recipe_tags or [])
                 if isinstance(t, dict) and t.get("id") == tid),
                tid,
            )
            reasons.append(f"Tag: {tag_name}")

    recipe_ing_ids = {
        i.get("ingredientId", "") or i.get("id", "")
        for i in (recipe.ingredients or []) if isinstance(i, dict)
    }
    for iid in parsed.ingredient_ids:
        if iid in recipe_ing_ids:
            ing_name = next(
                (i.get("text", "") or (i.get("mappedIngredient") or {}).get("name", "")
                 for i in (recipe.ingredients or [])
                 if isinstance(i, dict) and (i.get("ingredientId", "") == iid or i.get("id", "") == iid)),
                iid,
            )
            reasons.append(f"Ingredient: {ing_name}")

    return reasons or ["Relevant recipe"]


def _build_qdrant_filter(
    user_id: str,
    tag_ids: list[str] | None = None,
    ingredient_ids: list[str] | None = None,
    max_cook_time: int | None = None,
    max_prep_time: int | None = None,
    min_servings: int | None = None,
    max_servings: int | None = None,
) -> qdrant_models.Filter:
    """Build a Qdrant payload filter."""
    must: list[qdrant_models.Condition] = [
        qdrant_models.FieldCondition(
            key="userId",
            match=qdrant_models.MatchValue(value=user_id),
        )
    ]

    if tag_ids:
        for tid in tag_ids:
            must.append(
                qdrant_models.FieldCondition(
                    key="tagIds",
                    match=qdrant_models.MatchValue(value=tid),
                )
            )

    if ingredient_ids:
        for iid in ingredient_ids:
            must.append(
                qdrant_models.FieldCondition(
                    key="ingredientIds",
                    match=qdrant_models.MatchValue(value=iid),
                )
            )

    if max_cook_time is not None:
        must.append(
            qdrant_models.FieldCondition(
                key="cookTimeMinutes",
                range=qdrant_models.Range(lte=max_cook_time),
            )
        )

    if max_prep_time is not None:
        must.append(
            qdrant_models.FieldCondition(
                key="prepTimeMinutes",
                range=qdrant_models.Range(lte=max_prep_time),
            )
        )

    if min_servings is not None:
        must.append(
            qdrant_models.FieldCondition(
                key="servings",
                range=qdrant_models.Range(gte=min_servings),
            )
        )

    if max_servings is not None:
        must.append(
            qdrant_models.FieldCondition(
                key="servings",
                range=qdrant_models.Range(lte=max_servings),
            )
        )

    return qdrant_models.Filter(must=must)
