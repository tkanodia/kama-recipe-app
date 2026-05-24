from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceContext(BaseModel):
    source_type: str = Field(alias="sourceType")
    original_url: str | None = Field(default=None, alias="originalUrl")
    context_note: str | None = Field(default=None, alias="contextNote")

    model_config = {"populate_by_name": True}


class CandidateResponse(BaseModel):
    id: str
    ingestion_job_id: str = Field(alias="ingestionJobId")
    title: str
    ingredients: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    description: str | None = None
    prep_time_minutes: int | None = Field(default=None, alias="prepTimeMinutes")
    cook_time_minutes: int | None = Field(default=None, alias="cookTimeMinutes")
    servings: int | None = None
    recipe_tags: list[dict[str, Any]] = Field(default_factory=list, alias="recipeTags")
    canonical_eligible: bool = Field(alias="canonicalEligible")
    draft_eligible: bool = Field(alias="draftEligible")
    review_mode: str = Field(alias="reviewMode")
    review_findings: list[dict[str, Any]] = Field(default_factory=list, alias="reviewFindings")
    field_confidence_map: dict[str, Any] = Field(default_factory=dict, alias="fieldConfidenceMap")
    field_provenance_map: dict[str, Any] = Field(default_factory=dict, alias="fieldProvenanceMap")
    selected_extraction_method: str = Field(alias="selectedExtractionMethod")
    source_artifact_ids: list[str] = Field(default_factory=list, alias="sourceArtifactIds")
    preview_image_url: str | None = Field(default=None, alias="previewImageUrl")
    decision_status: str = Field(alias="decisionStatus")
    source_context: SourceContext | None = Field(default=None, alias="sourceContext")
    allowed_actions: list[str] = Field(default_factory=list, alias="allowedActions")
    review_agent_summary: dict[str, Any] | None = Field(default=None, alias="reviewAgentSummary")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class CandidateDecisionBody(BaseModel):
    action: str  # save_canonical, save_draft, discard
    edited_fields: dict[str, Any] | None = Field(default=None, alias="editedFields")

    model_config = {"populate_by_name": True}


class CandidateDecisionResponse(BaseModel):
    action: str
    canonical_recipe_id: str | None = Field(default=None, alias="canonicalRecipeId")
    draft_recipe_id: str | None = Field(default=None, alias="draftRecipeId")

    model_config = {"populate_by_name": True}
