from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import RecipeCandidate


async def create_stub_candidate(
    session: AsyncSession,
    *,
    id: str,
    user_id: str,
    source_asset_id: str,
    ingestion_job_id: str,
) -> RecipeCandidate:
    row = RecipeCandidate(
        id=id,
        user_id=user_id,
        source_asset_id=source_asset_id,
        ingestion_job_id=ingestion_job_id,
        title="Stub recipe (scaffold)",
        ingredients=[{"text": "stub ingredient", "ingredientId": None, "quantity": None, "unit": None}],
        steps=[{"order": 1, "text": "Stub step — replace with real extraction.", "mediaRefs": []}],
        canonical_eligible=True,
        draft_eligible=True,
        review_mode="standard",
        review_findings=[],
        field_confidence_map={},
        field_provenance_map={},
        selected_extraction_method="stub_scaffold",
        source_artifact_ids=[],
        decision_status="pending",
    )
    session.add(row)
    await session.flush()
    return row


async def create_candidate(
    session: AsyncSession,
    *,
    user_id: str,
    source_asset_id: str,
    ingestion_job_id: str,
    title: str,
    ingredients: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    description: str | None = None,
    prep_time_minutes: int | None = None,
    cook_time_minutes: int | None = None,
    servings: int | None = None,
    recipe_tags: list[dict] | None = None,
    nutrition: dict | None = None,
    notes: list[dict] | None = None,
    how_to_serve: str | None = None,
    canonical_eligible: bool = False,
    draft_eligible: bool = True,
    review_mode: str = "standard",
    review_findings: list[dict] | None = None,
    field_confidence_map: dict | None = None,
    field_provenance_map: dict | None = None,
    selected_extraction_method: str = "",
    source_artifact_ids: list[str] | None = None,
) -> RecipeCandidate:
    cand_id = new_id("cand")
    row = RecipeCandidate(
        id=cand_id,
        user_id=user_id,
        source_asset_id=source_asset_id,
        ingestion_job_id=ingestion_job_id,
        title=title,
        ingredients=ingredients or [],
        steps=steps or [],
        description=description,
        prep_time_minutes=prep_time_minutes,
        cook_time_minutes=cook_time_minutes,
        servings=servings,
        recipe_tags=recipe_tags or [],
        nutrition=nutrition,
        notes=notes or [],
        how_to_serve=how_to_serve,
        canonical_eligible=canonical_eligible,
        draft_eligible=draft_eligible,
        review_mode=review_mode,
        review_findings=review_findings or [],
        field_confidence_map=field_confidence_map or {},
        field_provenance_map=field_provenance_map or {},
        selected_extraction_method=selected_extraction_method,
        source_artifact_ids=source_artifact_ids or [],
        decision_status="pending",
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_id(session: AsyncSession, candidate_id: str) -> RecipeCandidate | None:
    return await session.get(RecipeCandidate, candidate_id)
