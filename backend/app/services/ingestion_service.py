"""Orchestrates candidate creation from agent extraction results."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import recipe_candidate_repo


async def create_candidate_from_extraction(
    session: AsyncSession,
    *,
    user_id: str,
    source_asset_id: str,
    ingestion_job_id: str,
    candidate_update: dict[str, Any],
    provenance: dict[str, Any],
    extraction_method: str,
    review_mode: str,
    review_findings: list[dict],
    canonical_eligible: bool,
    draft_eligible: bool,
    source_artifact_ids: list[str],
) -> str:
    candidate = await recipe_candidate_repo.create_candidate(
        session,
        user_id=user_id,
        source_asset_id=source_asset_id,
        ingestion_job_id=ingestion_job_id,
        title=candidate_update.get("title", "Untitled Recipe"),
        ingredients=candidate_update.get("ingredients", []),
        steps=candidate_update.get("steps", []),
        description=candidate_update.get("description"),
        prep_time_minutes=candidate_update.get("prepTimeMinutes"),
        cook_time_minutes=candidate_update.get("cookTimeMinutes"),
        servings=candidate_update.get("servings"),
        recipe_tags=candidate_update.get("recipeTags"),
        nutrition=candidate_update.get("nutrition"),
        notes=candidate_update.get("notes", []),
        how_to_serve=candidate_update.get("howToServe"),
        canonical_eligible=canonical_eligible,
        draft_eligible=draft_eligible,
        review_mode=review_mode,
        review_findings=review_findings,
        field_provenance_map=provenance,
        selected_extraction_method=extraction_method,
        source_artifact_ids=source_artifact_ids,
    )
    return candidate.id
