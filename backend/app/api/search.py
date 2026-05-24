"""Search API — hybrid recipe search endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter

log = structlog.get_logger()
router = APIRouter(prefix="/search", tags=["search"])


class SearchFilters(BaseModel):
    tag_ids: list[str] | None = Field(default=None, alias="tagIds")
    ingredient_ids: list[str] | None = Field(default=None, alias="ingredientIds")
    max_cook_time_minutes: int | None = Field(default=None, alias="maxCookTimeMinutes")
    max_prep_time_minutes: int | None = Field(default=None, alias="maxPrepTimeMinutes")
    min_servings: int | None = Field(default=None, alias="minServings")
    max_servings: int | None = Field(default=None, alias="maxServings")
    model_config = {"populate_by_name": True}


class SearchRequest(BaseModel):
    query: str | None = None
    filters: SearchFilters | None = None
    limit: int = Field(default=20, le=50)
    cursor: int = Field(default=0, ge=0)
    model_config = {"populate_by_name": True}


class SearchResultItem(BaseModel):
    id: str
    title: str
    description: str | None = None
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    hero_image_url: str | None = Field(default=None, alias="heroImageUrl")
    recipe_tags: list[dict[str, Any]] = Field(default_factory=list, alias="recipeTags")
    relevance_score: float = Field(alias="relevanceScore")
    match_reasons: list[str] = Field(default_factory=list, alias="matchReasons")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    model_config = {"populate_by_name": True}


class ParsedQueryResponse(BaseModel):
    semantic_query: str = Field(default="", alias="semanticQuery")
    query_intent: str = Field(default="search", alias="queryIntent")
    tag_ids: list[str] = Field(default_factory=list, alias="tagIds")
    ingredient_ids: list[str] = Field(default_factory=list, alias="ingredientIds")
    model_config = {"populate_by_name": True}


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    parsed_query: ParsedQueryResponse = Field(alias="parsedQuery")
    next_cursor: int | None = Field(default=None, alias="nextCursor")
    has_more: bool = Field(default=False, alias="hasMore")
    search_quality_reduced: bool = Field(default=False, alias="searchQualityReduced")
    model_config = {"populate_by_name": True}


@router.post("", response_model=SearchResponse)
@limiter.limit("60/minute")
async def search_recipes(
    request: Request,
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SearchResponse:
    if not body.query and not body.filters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of 'query' or 'filters' is required",
        )

    from app.services.search_service import search_recipes as do_search

    filters_dict = None
    if body.filters:
        filters_dict = body.filters.model_dump(by_alias=True, exclude_none=True)

    results = await do_search(
        query=body.query,
        filters=filters_dict,
        user_id=user_id,
        limit=body.limit,
        cursor=body.cursor,
        db=db,
    )

    items: list[SearchResultItem] = []
    for r in results.items:
        hero_url = await _get_hero_url(db, r.recipe.id)
        items.append(SearchResultItem(
            id=r.recipe.id,
            title=r.recipe.title,
            description=r.recipe.description,
            prepTimeMinutes=r.recipe.prep_time_minutes,
            cookTimeMinutes=r.recipe.cook_time_minutes,
            servings=r.recipe.servings,
            heroImageUrl=hero_url,
            recipeTags=_normalize_tags(r.recipe.recipe_tags),
            relevanceScore=r.relevance_score,
            matchReasons=r.match_reasons,
            createdAt=r.recipe.created_at,
            updatedAt=r.recipe.updated_at,
        ))

    parsed = ParsedQueryResponse(
        semanticQuery=results.parsed_query.semantic_query,
        queryIntent=results.parsed_query.query_intent,
        tagIds=results.parsed_query.tag_ids,
        ingredientIds=results.parsed_query.ingredient_ids,
    )

    return SearchResponse(
        items=items,
        parsedQuery=parsed,
        nextCursor=results.next_cursor,
        hasMore=results.has_more,
        searchQualityReduced=results.search_quality_reduced,
    )


def _normalize_tags(tags: list | None) -> list[dict[str, Any]]:
    if not tags:
        return []
    result = []
    for t in tags:
        if isinstance(t, dict):
            result.append(t)
        elif isinstance(t, str):
            result.append({"id": t, "name": t})
    return result


async def _get_hero_url(db: AsyncSession, recipe_id: str) -> str | None:
    from app.repositories import recipe_media_repo
    media = await recipe_media_repo.find_by_recipe(db, recipe_id)
    hero = next((m for m in media if m.role == "hero"), None)
    if not hero:
        return None
    from app.api.recipes import _resolve_asset_ref
    return _resolve_asset_ref(hero.asset_ref) or None
