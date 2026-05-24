from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubmitIngestionBody(BaseModel):
    source_type: str = Field(alias="sourceType")
    url: str | None = None
    file_asset_ref: str | None = Field(default=None, alias="fileAssetRef")
    raw_text_input: str | None = Field(default=None, alias="rawTextInput")
    context_note: str | None = Field(default=None, alias="contextNote")
    llm_model: str | None = Field(default=None, alias="llmModel")

    model_config = {"populate_by_name": True}


class SubmitIngestionResponse(BaseModel):
    source_asset_id: str = Field(alias="sourceAssetId")
    ingestion_job_id: str = Field(alias="ingestionJobId")
    status: str
    sse_url: str = Field(alias="sseUrl")

    model_config = {"populate_by_name": True}


class ExtractionPlanEntryResponse(BaseModel):
    method_key: str = Field(alias="methodKey")
    priority: int
    feasible: bool
    feasibility_reason: str | None = Field(default=None, alias="feasibilityReason")
    required_artifacts: list[str] = Field(default_factory=list, alias="requiredArtifacts")
    status: str
    started_at: datetime | None = Field(default=None, alias="startedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    output_summary: dict[str, Any] | None = Field(default=None, alias="outputSummary")
    failure: dict[str, Any] | None = None
    stop_decision: dict[str, Any] | None = Field(default=None, alias="stopDecision")

    model_config = {"populate_by_name": True}


class StateHistoryEventResponse(BaseModel):
    event_type: str = Field(alias="eventType")
    timestamp: str
    internal_state: str | None = Field(default=None, alias="internalState")
    method_key: str | None = Field(default=None, alias="methodKey")
    status: str | None = None

    model_config = {"populate_by_name": True}


class IngestionJobResponse(BaseModel):
    id: str
    source_asset_id: str = Field(alias="sourceAssetId")
    status: str
    internal_state: str = Field(alias="internalState")
    internal_error_state: str | None = Field(default=None, alias="internalErrorState")
    processor_family: str = Field(alias="processorFamily")
    processor_variant: str | None = Field(default=None, alias="processorVariant")
    review_mode: str | None = Field(default=None, alias="reviewMode")
    candidate_id: str | None = Field(default=None, alias="candidateId")
    normalized_artifact_ids: list[str] = Field(default_factory=list, alias="normalizedArtifactIds")
    error_type: str | None = Field(default=None, alias="errorType")
    error_code: str | None = Field(default=None, alias="errorCode")
    rerun_allowed: bool = Field(alias="rerunAllowed")
    user_recoverable: bool = Field(alias="userRecoverable")
    extraction_plan: list[dict[str, Any]] = Field(default_factory=list, alias="extractionPlan")
    state_history: list[dict[str, Any]] = Field(default_factory=list, alias="stateHistory")
    job_metadata: dict[str, Any] | None = Field(
        default=None,
        serialization_alias="metadata",
        validation_alias="metadata",
    )
    created_at: datetime = Field(alias="createdAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    updated_at: datetime = Field(alias="updatedAt")
    last_heartbeat_at: datetime | None = Field(default=None, alias="lastHeartbeatAt")

    model_config = {"populate_by_name": True}


class RerunIngestionResponse(BaseModel):
    original_job_id: str = Field(alias="originalJobId")
    new_job_id: str = Field(alias="newJobId")
    source_asset_id: str = Field(alias="sourceAssetId")
    status: str
    sse_url: str = Field(alias="sseUrl")

    model_config = {"populate_by_name": True}
