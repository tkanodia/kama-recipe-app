"""Candidate APIs — GET for review, POST decision (save_canonical / save_draft / discard)."""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.models.tables import RecipeCandidate
from app.repositories import (
    canonical_recipe_repo, draft_recipe_repo, ingredient_repo,
    recipe_candidate_repo, source_asset_repo, normalized_artifact_repo,
)
from app.schemas.candidates import (
    CandidateDecisionBody, CandidateDecisionResponse,
    CandidateResponse, SourceContext,
)

log = structlog.get_logger()
router = APIRouter(prefix="/recipe-candidates", tags=["candidates"])


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> CandidateResponse:
    cand = await recipe_candidate_repo.get_by_id(db, candidate_id)
    if cand is None or cand.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    source = await source_asset_repo.get_source_asset_by_id(db, cand.source_asset_id)
    source_context = None
    if source:
        source_context = SourceContext(
            sourceType=source.source_type,
            originalUrl=source.original_url,
            contextNote=source.context_note,
        )

    allowed = []
    if cand.decision_status == "pending":
        if cand.canonical_eligible:
            allowed.append("save_canonical")
        if cand.draft_eligible:
            allowed.append("save_draft")
        allowed.append("discard")

    preview_image_url = None
    if cand.source_artifact_ids:
        for art_id in cand.source_artifact_ids:
            art = await normalized_artifact_repo.get_by_id(db, art_id)
            if art and art.payload:
                image_urls = art.payload.get("imageUrls") or []
                if image_urls:
                    preview_image_url = image_urls[0]
                    break

    return CandidateResponse(
        id=cand.id,
        ingestionJobId=cand.ingestion_job_id,
        title=cand.title,
        ingredients=cand.ingredients,
        steps=cand.steps,
        description=cand.description,
        prepTimeMinutes=cand.prep_time_minutes,
        cookTimeMinutes=cand.cook_time_minutes,
        servings=cand.servings,
        recipeTags=cand.recipe_tags,
        canonicalEligible=cand.canonical_eligible,
        draftEligible=cand.draft_eligible,
        reviewMode=cand.review_mode,
        reviewFindings=cand.review_findings,
        fieldConfidenceMap=cand.field_confidence_map,
        fieldProvenanceMap=cand.field_provenance_map,
        selectedExtractionMethod=cand.selected_extraction_method,
        sourceArtifactIds=cand.source_artifact_ids,
        previewImageUrl=preview_image_url,
        decisionStatus=cand.decision_status,
        sourceContext=source_context,
        allowedActions=allowed,
        createdAt=cand.created_at,
    )


@router.post("/{candidate_id}/decision", response_model=CandidateDecisionResponse)
async def decide_candidate(
    candidate_id: str,
    body: CandidateDecisionBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> CandidateDecisionResponse:
    cand = await recipe_candidate_repo.get_by_id(db, candidate_id)
    if cand is None or cand.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    if cand.decision_status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already decided")

    edits = body.edited_fields or {}

    title = edits.get("title", cand.title)
    ingredients = edits.get("ingredients", cand.ingredients)
    steps = edits.get("steps", cand.steps)
    description = edits.get("description", cand.description)
    prep = edits.get("prepTimeMinutes", cand.prep_time_minutes)
    cook = edits.get("cookTimeMinutes", cand.cook_time_minutes)
    servings = edits.get("servings", cand.servings)
    tags = edits.get("recipeTags", cand.recipe_tags)
    nutrition = edits.get("nutrition", cand.nutrition)
    notes = edits.get("notes", cand.notes or [])
    how_to_serve = edits.get("howToServe", cand.how_to_serve)

    ingredients = await _enrich_ingredient_categories(db, ingredients)

    canonical_id = None
    draft_id = None

    if body.action == "save_canonical":
        if not cand.canonical_eligible:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not eligible for canonical save")

        recipe = await canonical_recipe_repo.create(
            db, user_id=user_id, title=title, ingredients=ingredients, steps=steps,
            description=description, prep_time_minutes=prep, cook_time_minutes=cook,
            servings=servings, recipe_tags=tags,
            nutrition=nutrition, notes=notes, how_to_serve=how_to_serve,
            field_provenance_map=cand.field_provenance_map,
            source_asset_id=cand.source_asset_id,
            origin_recipe_candidate_id=cand.id,
        )
        canonical_id = recipe.id

        try:
            from app.repositories import recipe_search_index_repo
            from app.workers.search_index_worker import index_recipe_send
            await recipe_search_index_repo.create(db, canonical_recipe_id=canonical_id, stale_reason="new_recipe")
            await db.flush()
            index_recipe_send(canonical_id)
        except Exception:
            log.warning("search_index_trigger_failed", recipe_id=canonical_id, exc_info=True)

        await _accumulate_ingredient_aliases(db, ingredients)

        try:
            from app.services.media_materialization_service import materialize_extracted_images
            image_urls: list[str] = []
            step_images: dict[str, list[str]] = {}
            if hasattr(cand, "source_artifact_ids") and cand.source_artifact_ids:
                for art_id in cand.source_artifact_ids:
                    art = await normalized_artifact_repo.get_by_id(db, art_id)
                    if art and art.payload:
                        if art.payload.get("imageUrls") and not image_urls:
                            image_urls = art.payload["imageUrls"]
                        if art.payload.get("stepImages") and not step_images:
                            step_images = art.payload["stepImages"]
            if image_urls or step_images:
                await materialize_extracted_images(
                    {"imageUrls": image_urls, "stepImages": step_images},
                    canonical_id, user_id, db,
                )
        except Exception:
            log.warning("media_materialization_failed", candidate_id=candidate_id, exc_info=True)

    elif body.action == "save_draft":
        if not cand.draft_eligible:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not eligible for draft save")

        draft = await draft_recipe_repo.create(
            db, user_id=user_id,
            origin_source_asset_id=cand.source_asset_id,
            origin_recipe_candidate_id=cand.id,
            title=title, ingredients=ingredients, steps=steps,
            description=description, prep_time_minutes=prep, cook_time_minutes=cook,
            servings=servings, recipe_tags=tags,
            nutrition=nutrition, notes=notes, how_to_serve=how_to_serve,
        )
        draft_id = draft.id

    elif body.action == "discard":
        refs_to_delete: list[str] = []
        if cand.source_asset_id:
            sa = await source_asset_repo.get_source_asset_by_id(db, cand.source_asset_id)
            if sa and sa.file_asset_ref:
                refs_to_delete.append(sa.file_asset_ref)
        for art_id in (cand.source_artifact_ids or []):
            art = await normalized_artifact_repo.get_by_id(db, art_id)
            if art and art.payload:
                for url in (art.payload.get("imageUrls") or []):
                    if url and not url.startswith(("http://", "https://")):
                        refs_to_delete.append(url)
        if refs_to_delete:
            try:
                from app.core.config import get_settings
                from app.core.s3 import delete_objects
                s = get_settings()
                if s.s3_bucket:
                    delete_objects(bucket=s.s3_bucket, keys=refs_to_delete)
            except Exception:
                log.warning("s3_discard_cleanup_failed", candidate_id=candidate_id, exc_info=True)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid action: {body.action}")

    await db.execute(
        sa_update(RecipeCandidate)
        .where(RecipeCandidate.id == candidate_id)
        .values(decision_status=body.action)
    )
    await db.commit()

    return CandidateDecisionResponse(
        action=body.action,
        canonicalRecipeId=canonical_id,
        draftRecipeId=draft_id,
    )


async def _enrich_ingredient_categories(
    db: AsyncSession,
    ingredients: list[dict],
) -> list[dict]:
    """Ensure every ingredient with an ingredientId has a complete mappedIngredient
    including name and category from the DB. Handles cases where the frontend
    sends back partial mappedIngredient data (e.g. missing category)."""
    for ing in ingredients:
        ing_id = ing.get("ingredientId") or (ing.get("mappedIngredient") or {}).get("id")
        if not ing_id:
            continue
        db_ing = await ingredient_repo.get_by_id(db, ing_id)
        if db_ing is None:
            continue
        ing["ingredientId"] = db_ing.id
        ing["mappedIngredient"] = {
            "id": db_ing.id,
            "name": db_ing.name,
            "category": db_ing.category,
        }
    return ingredients


async def _accumulate_ingredient_aliases(
    db: AsyncSession,
    ingredients: list[dict],
) -> None:
    """Append ingredient text as alias when it differs from the canonical name."""
    for ing in ingredients:
        ingredient_id = ing.get("ingredientId")
        text = (ing.get("text") or "").strip()
        if not ingredient_id or not text:
            continue

        db_ingredient = await ingredient_repo.get_by_id(db, ingredient_id)
        if db_ingredient is None:
            continue

        if text.lower() == db_ingredient.name.lower():
            continue

        existing_aliases = {a.strip().lower() for a in db_ingredient.aliases}
        if text.lower() in existing_aliases:
            continue

        await ingredient_repo.update_aliases(db, ingredient_id, [text])
        log.debug(
            "ingredient_alias_added",
            ingredient_id=ingredient_id,
            alias=text,
        )
