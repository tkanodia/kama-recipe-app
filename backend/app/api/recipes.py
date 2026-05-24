"""Recipe APIs — list, detail, edit, delete, revisions, media, journal."""

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.search import ParsedQueryResponse
from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.repositories import (
    canonical_recipe_repo, draft_recipe_repo, journal_repo,
    recipe_media_repo, recipe_revision_repo, source_asset_repo,
)

log = structlog.get_logger()
router = APIRouter(prefix="/recipes", tags=["recipes"])


def _normalize_tags(tags: list | None) -> list[dict[str, Any]]:
    """Ensure recipe_tags is always a list of {id, name} dicts."""
    if not tags:
        return []
    result = []
    for t in tags:
        if isinstance(t, dict):
            result.append(t)
        elif isinstance(t, str):
            result.append({"id": t, "name": t})
        else:
            result.append({"id": str(t), "name": str(t)})
    return result


def _resolve_asset_ref(ref: str | None) -> str:
    """Resolve an S3 asset ref to a presigned URL, or return the ref as-is."""
    if not ref:
        return ""
    if ref.startswith(("http://", "https://")):
        return ref
    from app.core.config import get_settings
    from app.core.s3 import generate_presigned_get_url
    settings = get_settings()
    if settings.s3_bucket:
        try:
            return generate_presigned_get_url(bucket=settings.s3_bucket, key=ref)
        except Exception:
            return ref
    return ref


async def _parse_search_query_meta(query: str, user_id: str) -> ParsedQueryResponse:
    from app.services.query_parser_service import parse_query

    try:
        parsed = await parse_query(query, user_id)
        return ParsedQueryResponse(
            semanticQuery=parsed.semantic_query,
            queryIntent=parsed.query_intent,
            tagIds=parsed.tag_ids,
            ingredientIds=parsed.ingredient_ids,
        )
    except Exception:
        log.warning("search_query_parse_failed_on_fallback", query=query, exc_info=True)
        return ParsedQueryResponse(semanticQuery=query, queryIntent="search")


# --- Schemas ---

class RecipeCardResponse(BaseModel):
    id: str
    kind: str = "canonical"
    title: str
    description: str | None = None
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    hero_image_url: str | None = Field(default=None, alias="heroImageUrl")
    recipe_tags: list[dict[str, Any]] = Field(default_factory=list, alias="recipeTags")
    journal_entry_count: int = Field(default=0, alias="journalEntryCount")
    feasibility_status: str | None = Field(default=None, alias="feasibilityStatus")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    model_config = {"populate_by_name": True}


class RecipeDetailResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    ingredients: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    recipe_tags: list[dict[str, Any]] = Field(default_factory=list, alias="recipeTags")
    hero_image: dict[str, Any] | None = Field(default=None, alias="heroImage")
    gallery: list[dict[str, Any]] = Field(default_factory=list)
    field_provenance_map: dict[str, Any] = Field(default_factory=dict, alias="fieldProvenanceMap")
    source_asset_id: str | None = Field(default=None, alias="sourceAssetId")
    source_url: str | None = Field(default=None, alias="sourceUrl")
    source_type: str | None = Field(default=None, alias="sourceType")
    source_image_url: str | None = Field(default=None, alias="sourceImageUrl")
    nutrition: dict[str, Any] | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)
    how_to_serve: str | None = Field(default=None, alias="howToServe")
    journal_summary: str | None = Field(default=None, alias="journalSummary")
    revision_count: int = Field(default=0, alias="revisionCount")
    journal_entry_count: int = Field(default=0, alias="journalEntryCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    model_config = {"populate_by_name": True}


class UpdateRecipeBody(BaseModel):
    title: str | None = None
    description: str | None = None
    ingredients: list[dict[str, Any]] | None = None
    steps: list[dict[str, Any]] | None = None
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    recipe_tags: list[dict[str, Any]] | None = Field(default=None, alias="recipeTags")
    nutrition: dict[str, Any] | None = None
    notes: list[dict[str, Any]] | None = None
    how_to_serve: str | None = Field(default=None, alias="howToServe")
    model_config = {"populate_by_name": True}


class UpdateRecipeResponse(BaseModel):
    id: str
    revision_created: bool = Field(alias="revisionCreated")
    revision_id: str | None = Field(default=None, alias="revisionId")
    model_config = {"populate_by_name": True}


class RevisionResponse(BaseModel):
    id: str
    change_summary: str | None = Field(default=None, alias="changeSummary")
    created_at: datetime = Field(alias="createdAt")
    model_config = {"populate_by_name": True}


class MediaResponse(BaseModel):
    id: str
    role: str
    source: str
    asset_ref: str = Field(alias="assetRef")
    thumbnail_ref: str | None = Field(default=None, alias="thumbnailRef")
    display_order: int | None = Field(default=None, alias="displayOrder")
    model_config = {"populate_by_name": True}


class RegisterMediaBody(BaseModel):
    role: str
    source: str = "uploaded"
    asset_ref: str = Field(alias="assetRef")
    display_order: int | None = Field(default=None, alias="displayOrder")
    model_config = {"populate_by_name": True}


class UpdateMediaBody(BaseModel):
    role: str


class JournalMediaResponse(BaseModel):
    id: str
    url: str
    display_order: int = Field(default=0, alias="displayOrder")
    model_config = {"populate_by_name": True}


class JournalEntryResponse(BaseModel):
    id: str
    body: str
    cooked_on: str | None = Field(default=None, alias="cookedOn")
    tags: list[dict[str, Any]]
    media: list[JournalMediaResponse] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    model_config = {"populate_by_name": True}


class JournalListResponse(BaseModel):
    items: list[JournalEntryResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_more: bool = Field(default=False, alias="hasMore")
    model_config = {"populate_by_name": True}


class CreateJournalBody(BaseModel):
    body: str
    cooked_on: str | None = Field(default=None, alias="cookedOn")
    tags: list[dict[str, Any]] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list, alias="mediaRefs")
    model_config = {"populate_by_name": True}


def _trigger_search_reindex(recipe_id: str, reason: str = "content_changed") -> None:
    """Mark a recipe's search index as stale and enqueue re-indexing."""
    try:
        from app.services.background_runner import enqueue

        async def _mark_and_enqueue(rid: str, r: str) -> None:
            from app.core.database import SessionLocal
            from app.repositories import recipe_search_index_repo
            async with SessionLocal() as session:
                await recipe_search_index_repo.mark_stale(session, rid, reason=r)
                await session.commit()

        enqueue(_mark_and_enqueue, recipe_id, reason, task_name=f"mark-stale-{recipe_id}")

        from app.workers.search_index_worker import index_recipe_send
        index_recipe_send(recipe_id)
    except Exception:
        log.warning("search_index_trigger_failed", recipe_id=recipe_id, exc_info=True)


def _trigger_search_delete(recipe_id: str) -> None:
    """Delete a recipe's point from Qdrant and remove index status."""
    try:
        from app.services.background_runner import enqueue

        async def _delete_point_and_status(rid: str) -> None:
            from app.core.database import SessionLocal
            from app.repositories import recipe_search_index_repo
            from app.services.qdrant_client_service import delete_recipe_point
            try:
                await delete_recipe_point(rid)
            except Exception:
                pass
            async with SessionLocal() as session:
                await recipe_search_index_repo.delete_by_recipe_id(session, rid)
                await session.commit()

        enqueue(_delete_point_and_status, recipe_id, task_name=f"search-delete-{recipe_id}")
    except Exception:
        log.warning("search_delete_trigger_failed", recipe_id=recipe_id, exc_info=True)


# --- Endpoints ---

class RecipeListResponse(BaseModel):
    items: list[RecipeCardResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_more: bool = Field(default=False, alias="hasMore")
    parsed_query: ParsedQueryResponse | None = Field(default=None, alias="parsedQuery")
    search_quality_reduced: bool | None = Field(default=None, alias="searchQualityReduced")
    model_config = {"populate_by_name": True}


@router.get("")
@limiter.limit("120/minute")
async def list_recipes(
    request: Request,
    status_filter: str = Query(default="all", alias="status"),
    tags: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="updated_desc"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=50),
    pantry: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RecipeListResponse:
    results: list[RecipeCardResponse] = []
    tag_ids = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    fetch_limit = limit + 1

    # Use hybrid search when a search query is provided on canonical recipes
    use_hybrid = bool(search) and status_filter in ("all", "canonical")
    hybrid_done = False
    search_meta: ParsedQueryResponse | None = None
    search_quality_reduced: bool | None = None

    if use_hybrid:
        try:
            from app.services.search_service import search_recipes as hybrid_search
            search_results = await hybrid_search(
                query=search,
                filters={"tagIds": tag_ids} if tag_ids else None,
                user_id=user_id,
                limit=fetch_limit,
                cursor=0,
                db=db,
            )
            search_meta = ParsedQueryResponse(
                semanticQuery=search_results.parsed_query.semantic_query,
                queryIntent=search_results.parsed_query.query_intent,
                tagIds=search_results.parsed_query.tag_ids,
                ingredientIds=search_results.parsed_query.ingredient_ids,
            )
            search_quality_reduced = search_results.search_quality_reduced
            for sr in search_results.items:
                r = sr.recipe
                hero = await _get_hero_url(db, r.id)
                jcount = await canonical_recipe_repo.count_journal_entries(db, r.id)
                results.append(RecipeCardResponse(
                    id=r.id, kind="canonical", title=r.title, description=r.description,
                    prepTimeMinutes=r.prep_time_minutes, cookTimeMinutes=r.cook_time_minutes,
                    servings=r.servings, heroImageUrl=hero, recipeTags=_normalize_tags(r.recipe_tags),
                    journalEntryCount=jcount, createdAt=r.created_at, updatedAt=r.updated_at,
                ))
            hybrid_done = True
        except Exception:
            log.warning("hybrid_search_fallback_to_ilike", exc_info=True)
            search_quality_reduced = True
            search_meta = await _parse_search_query_meta(search, user_id)

    if not hybrid_done and status_filter in ("all", "canonical"):
        recipes = await canonical_recipe_repo.list_by_user(
            db, user_id, search=search, tag_ids=tag_ids, sort=sort, cursor=cursor, limit=fetch_limit,
        )
        for r in recipes:
            hero = await _get_hero_url(db, r.id)
            jcount = await canonical_recipe_repo.count_journal_entries(db, r.id)
            results.append(RecipeCardResponse(
                id=r.id, kind="canonical", title=r.title, description=r.description,
                prepTimeMinutes=r.prep_time_minutes, cookTimeMinutes=r.cook_time_minutes,
                servings=r.servings, heroImageUrl=hero, recipeTags=_normalize_tags(r.recipe_tags),
                journalEntryCount=jcount, createdAt=r.created_at, updatedAt=r.updated_at,
            ))

    if status_filter in ("all", "draft"):
        drafts = await draft_recipe_repo.list_by_user(db, user_id, limit=fetch_limit)
        for d in drafts:
            results.append(RecipeCardResponse(
                id=d.id, kind="draft", title=d.title, description=d.description,
                prepTimeMinutes=d.prep_time_minutes, cookTimeMinutes=d.cook_time_minutes,
                servings=d.servings, recipeTags=_normalize_tags(d.recipe_tags),
                journalEntryCount=0, createdAt=d.created_at, updatedAt=d.updated_at,
            ))

    if not hybrid_done:
        if sort == "updated_desc":
            results.sort(key=lambda x: x.updated_at, reverse=True)
        elif sort == "created_desc":
            results.sort(key=lambda x: x.created_at, reverse=True)
        elif sort == "title_asc":
            results.sort(key=lambda x: x.title.lower())

    has_more = len(results) > limit
    trimmed = results[:limit]

    if pantry:
        from app.repositories import pantry_repo
        pantry_ids = await pantry_repo.get_ingredient_ids_for_user(db, user_id)
        if pantry_ids:
            for card in trimmed:
                if card.kind != "canonical":
                    continue
                recipe = await canonical_recipe_repo.get_by_id(db, card.id)
                if not recipe or not recipe.ingredients:
                    continue
                ing_ids = {
                    ing.get("ingredientId") or ing.get("id")
                    for ing in recipe.ingredients
                    if ing.get("ingredientId") or ing.get("id")
                }
                if not ing_ids:
                    continue
                matched = sum(1 for iid in ing_ids if iid in pantry_ids)
                score = matched / len(ing_ids)
                if score == 1.0:
                    card.feasibility_status = "fully_feasible"
                elif score >= 0.5:
                    card.feasibility_status = "partially_feasible"
                else:
                    card.feasibility_status = "not_feasible"

    next_cursor: str | None = None
    if has_more and trimmed:
        last = trimmed[-1]
        if sort == "created_desc":
            next_cursor = last.created_at.isoformat()
        else:
            next_cursor = last.updated_at.isoformat()

    return RecipeListResponse(
        items=trimmed,
        nextCursor=next_cursor,
        hasMore=has_more,
        parsedQuery=search_meta,
        searchQualityReduced=search_quality_reduced,
    )


@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
@limiter.limit("120/minute")
async def get_recipe(
    request: Request,
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RecipeDetailResponse:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    media = await recipe_media_repo.find_by_recipe(db, recipe_id)

    def _resolve_ref(ref: str | None) -> str | None:
        if not ref:
            return None
        return _resolve_asset_ref(ref)

    hero = next(
        ({"id": m.id, "assetRef": _resolve_ref(m.asset_ref), "thumbnailRef": _resolve_ref(m.thumbnail_ref), "role": m.role} for m in media if m.role == "hero"),
        None,
    )
    gallery = [{"id": m.id, "assetRef": _resolve_ref(m.asset_ref), "thumbnailRef": _resolve_ref(m.thumbnail_ref), "role": m.role} for m in media if m.role != "hero"]

    rev_count = await canonical_recipe_repo.count_revisions(db, recipe_id)
    j_count = await canonical_recipe_repo.count_journal_entries(db, recipe_id)

    source_url: str | None = None
    source_type: str | None = None
    source_image_url: str | None = None
    if recipe.source_asset_id:
        sa = await source_asset_repo.get_source_asset_by_id(db, recipe.source_asset_id)
        if sa:
            source_url = sa.original_url
            source_type = sa.source_type
            if sa.source_type == "image" and sa.file_asset_ref:
                source_image_url = _resolve_ref(sa.file_asset_ref)

    return RecipeDetailResponse(
        id=recipe.id, title=recipe.title, description=recipe.description,
        ingredients=recipe.ingredients, steps=recipe.steps,
        prepTimeMinutes=recipe.prep_time_minutes, cookTimeMinutes=recipe.cook_time_minutes,
        servings=recipe.servings, recipeTags=_normalize_tags(recipe.recipe_tags),
        heroImage=hero, gallery=gallery,
        fieldProvenanceMap=recipe.field_provenance_map,
        sourceAssetId=recipe.source_asset_id,
        sourceUrl=source_url,
        sourceType=source_type,
        sourceImageUrl=source_image_url,
        nutrition=recipe.nutrition,
        notes=recipe.notes or [],
        howToServe=recipe.how_to_serve,
        journalSummary=recipe.journal_summary,
        revisionCount=rev_count, journalEntryCount=j_count,
        createdAt=recipe.created_at, updatedAt=recipe.updated_at,
    )


@router.patch("/{recipe_id}", response_model=UpdateRecipeResponse)
@limiter.limit("60/minute")
async def update_recipe(
    request: Request,
    recipe_id: str,
    body: UpdateRecipeBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> UpdateRecipeResponse:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    revision_fields = {"title", "ingredients", "steps", "prep_time_minutes", "cook_time_minutes", "servings"}
    changes = body.model_dump(exclude_none=True, by_alias=False)

    if "ingredients" in changes:
        from app.api.candidates import _enrich_ingredient_categories
        changes["ingredients"] = await _enrich_ingredient_categories(db, changes["ingredients"])

    needs_revision = any(k in revision_fields for k in changes)
    revision_id = None

    if needs_revision:
        snapshot = {
            "title": recipe.title, "ingredients": recipe.ingredients, "steps": recipe.steps,
            "description": recipe.description, "prepTimeMinutes": recipe.prep_time_minutes,
            "cookTimeMinutes": recipe.cook_time_minutes, "servings": recipe.servings,
            "recipeTags": recipe.recipe_tags,
        }
        changed_fields = [k for k in changes if k in revision_fields]
        summary = f"Changed: {', '.join(changed_fields)}"
        rev = await recipe_revision_repo.create_snapshot(
            db, canonical_recipe_id=recipe_id, snapshot_payload=snapshot, change_summary=summary,
        )
        revision_id = rev.id

    await canonical_recipe_repo.update_fields(db, recipe_id, **changes)
    await db.commit()

    _trigger_search_reindex(recipe_id, reason="recipe_edited")

    return UpdateRecipeResponse(id=recipe_id, revisionCreated=needs_revision, revisionId=revision_id)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_recipe(
    request: Request,
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    _trigger_search_delete(recipe_id)

    asset_refs = await canonical_recipe_repo.delete_cascade(db, recipe_id)
    await db.commit()

    if asset_refs:
        try:
            from app.core.config import get_settings
            from app.core.s3 import delete_objects
            s = get_settings()
            if s.s3_bucket:
                delete_objects(bucket=s.s3_bucket, keys=[r for r in asset_refs if r])
        except Exception:
            log.warning("s3_cleanup_failed", recipe_id=recipe_id, exc_info=True)


# --- Revisions ---

@router.get("/{recipe_id}/revisions", response_model=list[RevisionResponse])
@limiter.limit("120/minute")
async def list_revisions(
    request: Request,
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[RevisionResponse]:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    revs = await recipe_revision_repo.list_by_recipe(db, recipe_id)
    return [RevisionResponse(id=r.id, changeSummary=r.change_summary, createdAt=r.created_at) for r in revs]


@router.post("/{recipe_id}/revisions/{revision_id}/restore", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def restore_revision(
    request: Request,
    recipe_id: str,
    revision_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    rev = await recipe_revision_repo.get_by_id(db, revision_id)
    if rev is None or rev.canonical_recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    current_snapshot = {
        "title": recipe.title, "ingredients": recipe.ingredients, "steps": recipe.steps,
        "description": recipe.description, "prepTimeMinutes": recipe.prep_time_minutes,
        "cookTimeMinutes": recipe.cook_time_minutes, "servings": recipe.servings,
        "recipeTags": recipe.recipe_tags,
    }
    await recipe_revision_repo.create_snapshot(
        db, canonical_recipe_id=recipe_id, snapshot_payload=current_snapshot,
        change_summary=f"Snapshot before restoring revision {revision_id}",
    )

    payload = rev.snapshot_payload
    await canonical_recipe_repo.update_fields(
        db, recipe_id,
        title=payload.get("title"), ingredients=payload.get("ingredients"),
        steps=payload.get("steps"), description=payload.get("description"),
        prep_time_minutes=payload.get("prepTimeMinutes"),
        cook_time_minutes=payload.get("cookTimeMinutes"),
        servings=payload.get("servings"), recipe_tags=payload.get("recipeTags"),
    )
    await db.commit()
    return {"restored": True, "revisionId": revision_id}


# --- Media ---

@router.post("/{recipe_id}/media", status_code=status.HTTP_201_CREATED, response_model=MediaResponse)
@limiter.limit("60/minute")
async def register_media(
    request: Request,
    recipe_id: str,
    body: RegisterMediaBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MediaResponse:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    if body.role == "hero":
        await recipe_media_repo.demote_hero(db, recipe_id)

    m = await recipe_media_repo.create(
        db, canonical_recipe_id=recipe_id, role=body.role,
        source=body.source, asset_ref=body.asset_ref, display_order=body.display_order,
    )
    await db.commit()
    return MediaResponse(id=m.id, role=m.role, source=m.source, assetRef=m.asset_ref, thumbnailRef=m.thumbnail_ref, displayOrder=m.display_order)


@router.patch("/{recipe_id}/media/{media_id}", response_model=MediaResponse)
@limiter.limit("60/minute")
async def update_media(
    request: Request,
    recipe_id: str, media_id: str,
    body: UpdateMediaBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MediaResponse:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    m = await recipe_media_repo.get_by_id(db, media_id)
    if m is None or m.canonical_recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    if body.role == "hero":
        await recipe_media_repo.demote_hero(db, recipe_id)
    await recipe_media_repo.update_role(db, media_id, body.role)
    await db.commit()
    m = await recipe_media_repo.get_by_id(db, media_id)
    return MediaResponse(id=m.id, role=m.role, source=m.source, assetRef=m.asset_ref, thumbnailRef=m.thumbnail_ref, displayOrder=m.display_order)


@router.delete("/{recipe_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_media(
    request: Request,
    recipe_id: str, media_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    m = await recipe_media_repo.get_by_id(db, media_id)
    if m is None or m.canonical_recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    refs_to_delete = [r for r in [m.asset_ref, m.thumbnail_ref] if r]
    await recipe_media_repo.delete_media(db, media_id)
    await db.commit()

    if refs_to_delete:
        try:
            from app.core.config import get_settings
            from app.core.s3 import delete_objects
            s = get_settings()
            if s.s3_bucket:
                delete_objects(bucket=s.s3_bucket, keys=refs_to_delete)
        except Exception:
            log.warning("s3_media_cleanup_failed", media_id=media_id, exc_info=True)


# --- Journal ---

@router.get("/{recipe_id}/journal", response_model=JournalListResponse)
@limiter.limit("120/minute")
async def list_journal(
    request: Request,
    recipe_id: str,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> JournalListResponse:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    entries = await journal_repo.list_by_recipe(db, recipe_id, limit=limit + 1)
    has_more = len(entries) > limit
    trimmed = entries[:limit]
    results = []
    for e in trimmed:
        media_rows = await journal_repo.get_media_for_entry(db, e.id)
        media_objs = [
            JournalMediaResponse(
                id=m.id,
                url=_resolve_asset_ref(m.asset_ref),
                displayOrder=m.display_order or 0,
            )
            for m in media_rows
        ]
        results.append(JournalEntryResponse(
            id=e.id, body=e.body, cookedOn=e.cooked_on, tags=e.tags,
            media=media_objs, createdAt=e.created_at,
        ))
    next_cursor = trimmed[-1].id if has_more and trimmed else None
    return JournalListResponse(items=results, nextCursor=next_cursor, hasMore=has_more)


@router.post("/{recipe_id}/journal", status_code=status.HTTP_201_CREATED, response_model=JournalEntryResponse)
@limiter.limit("60/minute")
async def create_journal_entry(
    request: Request,
    recipe_id: str,
    body: CreateJournalBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> JournalEntryResponse:
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    entry = await journal_repo.create_entry(
        db, canonical_recipe_id=recipe_id, user_id=user_id,
        body=body.body, cooked_on=body.cooked_on, tags=body.tags,
        media_refs=body.media_refs[:2],
    )
    await db.commit()

    try:
        from app.workers.journal_summary_worker import regenerate_journal_summary_send
        regenerate_journal_summary_send(recipe_id)
    except Exception:
        log.warning("journal_summary_dispatch_failed", recipe_id=recipe_id, exc_info=True)

    media_rows = await journal_repo.get_media_for_entry(db, entry.id)
    media_objs = [
        JournalMediaResponse(
            id=m.id,
            url=_resolve_asset_ref(m.asset_ref),
            displayOrder=m.display_order or 0,
        )
        for m in media_rows
    ]
    return JournalEntryResponse(
        id=entry.id, body=entry.body, cookedOn=entry.cooked_on,
        tags=entry.tags, media=media_objs, createdAt=entry.created_at,
    )


class RegenerateJournalSummaryResponse(BaseModel):
    status: str
    model_config = {"populate_by_name": True}


@router.post(
    "/{recipe_id}/regenerate-journal-summary",
    response_model=RegenerateJournalSummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def regenerate_journal_summary(
    request: Request,
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RegenerateJournalSummaryResponse:
    """Enqueue journal summary regeneration for a recipe owned by the current user."""
    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    from app.workers.journal_summary_worker import regenerate_journal_summary_send

    regenerate_journal_summary_send(recipe_id)
    log.info("journal_summary_regeneration_queued", recipe_id=recipe_id, user_id=user_id)
    return RegenerateJournalSummaryResponse(status="queued")


async def _get_hero_url(db: AsyncSession, recipe_id: str) -> str | None:
    media = await recipe_media_repo.find_by_recipe(db, recipe_id)
    hero = next((m for m in media if m.role == "hero"), None)
    if not hero:
        return None
    return _resolve_asset_ref(hero.asset_ref) or None
