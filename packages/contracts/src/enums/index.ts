/** User-facing ingestion job lifecycle */
export type JobStatus =
  | "queued"
  | "processing"
  | "review_ready"
  | "draft_ready"
  | "failed"
  | "unsupported";

/** Internal pipeline stage */
export type InternalState =
  | "source_received"
  | "source_normalization"
  | "extraction_plan_building"
  | "recipe_extraction"
  | "quality_assessment"
  | "review_agent_processing"
  | "completed";

export type ErrorType = "internal" | "source_access" | "source_quality" | "parseability";

export type ReviewMode = "quick" | "standard" | "reconstruction";

export type SourceType = "url" | "image" | "text";

export type MediaRole =
  | "hero"
  | "source_gallery"
  | "step_reference"
  | "user_added_gallery";

export type TagDomain = "recipe" | "journal";

export type PresignedUrlContext = "recipe_media" | "journal_media" | "source_upload";

export type ExtractionMethodStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "skipped"
  | "not_applicable"
  | "deferred"
  | "merged";

export type ConfidenceLevel = "low" | "medium" | "high";

export type FieldConfidence = "low" | "medium" | "high";

export type ReviewFindingSeverity = "info" | "warning" | "error";
