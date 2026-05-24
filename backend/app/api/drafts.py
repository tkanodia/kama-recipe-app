"""Draft recipe APIs — list, detail, update, delete, promote, review-for-canonical."""

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.repositories import canonical_recipe_repo, draft_recipe_repo

log = structlog.get_logger()
router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    ingredients: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    recipe_tags: list[dict[str, Any]] = Field(default_factory=list, alias="recipeTags")
    promotion_eligible: bool = Field(alias="promotionEligible")
    origin_source_asset_id: str = Field(alias="originSourceAssetId")
    origin_recipe_candidate_id: str = Field(alias="originRecipeCandidateId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    model_config = {"populate_by_name": True}


class UpdateDraftBody(BaseModel):
    title: str | None = None
    description: str | None = None
    ingredients: list[dict[str, Any]] | None = None
    steps: list[dict[str, Any]] | None = None
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    recipe_tags: list[dict[str, Any]] | None = Field(default=None, alias="recipeTags")
    model_config = {"populate_by_name": True}


class ReviewForCanonicalResponse(BaseModel):
    findings: list[dict[str, Any]]
    finding_summary: dict[str, int] = Field(alias="findingSummary")
    canonical_eligible: bool = Field(alias="canonicalEligible")
    allowed_actions: list[str] = Field(alias="allowedActions")
    field_confidence_map: dict[str, str] = Field(alias="fieldConfidenceMap")
    model_config = {"populate_by_name": True}


class PromoteResponse(BaseModel):
    canonical_recipe_id: str = Field(alias="canonicalRecipeId")
    draft_deleted: bool = Field(alias="draftDeleted")
    model_config = {"populate_by_name": True}


@router.get("", response_model=list[DraftResponse])
@limiter.limit("120/minute")
async def list_drafts(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[DraftResponse]:
    drafts = await draft_recipe_repo.list_by_user(db, user_id)
    return [_draft_response(d) for d in drafts]


@router.get("/{draft_id}", response_model=DraftResponse)
@limiter.limit("120/minute")
async def get_draft(
    request: Request,
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> DraftResponse:
    d = await draft_recipe_repo.get_by_id(db, draft_id)
    if d is None or d.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return _draft_response(d)


@router.patch("/{draft_id}", response_model=DraftResponse)
@limiter.limit("60/minute")
async def update_draft(
    request: Request,
    draft_id: str,
    body: UpdateDraftBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> DraftResponse:
    d = await draft_recipe_repo.get_by_id(db, draft_id)
    if d is None or d.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    changes = body.model_dump(exclude_none=True, by_alias=False)
    if "ingredients" in changes:
        from app.api.candidates import _enrich_ingredient_categories
        changes["ingredients"] = await _enrich_ingredient_categories(db, changes["ingredients"])
    if changes:
        await draft_recipe_repo.update_fields(db, draft_id, **changes)
        await db.commit()
    d = await draft_recipe_repo.get_by_id(db, draft_id)
    return _draft_response(d)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_draft(
    request: Request,
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    d = await draft_recipe_repo.get_by_id(db, draft_id)
    if d is None or d.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    await draft_recipe_repo.delete_draft(db, draft_id)
    await db.commit()


@router.post("/{draft_id}/review-for-canonical", response_model=ReviewForCanonicalResponse)
@limiter.limit("60/minute")
async def review_for_canonical(
    request: Request,
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ReviewForCanonicalResponse:
    d = await draft_recipe_repo.get_by_id(db, draft_id)
    if d is None or d.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    from app.agents.review_agent import run_review_agent

    result = await run_review_agent(
        title=d.title,
        ingredients=d.ingredients,
        steps=d.steps,
        description=d.description,
        prep_time_minutes=d.prep_time_minutes,
        cook_time_minutes=d.cook_time_minutes,
        servings=d.servings,
    )

    eligible = result["canonicalEligible"]
    await draft_recipe_repo.update_fields(db, draft_id, promotion_eligible=eligible)
    await db.commit()

    allowed_actions = ["promote"] if eligible else ["edit_more"]
    log.info("draft_review_complete", draft_id=draft_id, eligible=eligible)

    return ReviewForCanonicalResponse(
        findings=result["reviewFindings"],
        findingSummary=result["findingSummary"],
        canonicalEligible=eligible,
        allowedActions=allowed_actions,
        fieldConfidenceMap=result["fieldConfidenceMap"],
    )


@router.post("/{draft_id}/promote", status_code=status.HTTP_201_CREATED, response_model=PromoteResponse)
@limiter.limit("60/minute")
async def promote_draft(
    request: Request,
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> PromoteResponse:
    d = await draft_recipe_repo.get_by_id(db, draft_id)
    if d is None or d.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if not d.promotion_eligible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft not promotion eligible — call review-for-canonical first",
        )

    from app.api.candidates import _enrich_ingredient_categories
    enriched_ings = await _enrich_ingredient_categories(db, d.ingredients)

    recipe = await canonical_recipe_repo.create(
        db,
        user_id=user_id,
        title=d.title,
        ingredients=enriched_ings,
        steps=d.steps,
        description=d.description,
        prep_time_minutes=d.prep_time_minutes,
        cook_time_minutes=d.cook_time_minutes,
        servings=d.servings,
        recipe_tags=d.recipe_tags,
        nutrition=d.nutrition,
        notes=d.notes or [],
        how_to_serve=d.how_to_serve,
        source_asset_id=d.origin_source_asset_id,
        origin_recipe_candidate_id=d.origin_recipe_candidate_id,
        promoted_from_draft=True,
        promoted_at=datetime.now(tz=UTC),
    )
    await draft_recipe_repo.delete_draft(db, draft_id)
    await db.commit()
    return PromoteResponse(canonicalRecipeId=recipe.id, draftDeleted=True)


def _draft_response(d) -> DraftResponse:
    return DraftResponse(
        id=d.id, title=d.title, description=d.description,
        ingredients=d.ingredients, steps=d.steps,
        prepTimeMinutes=d.prep_time_minutes, cookTimeMinutes=d.cook_time_minutes,
        servings=d.servings, recipeTags=d.recipe_tags,
        promotionEligible=d.promotion_eligible,
        originSourceAssetId=d.origin_source_asset_id,
        originRecipeCandidateId=d.origin_recipe_candidate_id,
        createdAt=d.created_at, updatedAt=d.updated_at,
    )
