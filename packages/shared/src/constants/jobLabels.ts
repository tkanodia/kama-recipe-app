import type { JobStatus } from "@kama/contracts";

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: "Waiting to start",
  processing: "Processing",
  review_ready: "Ready for review",
  draft_ready: "Can be saved as draft",
  failed: "We hit a system issue",
  unsupported: "Couldn't extract a usable recipe",
};

export const REVIEW_MODE_LABEL = {
  quick: "Quick review",
  standard: "Standard review",
  reconstruction: "Reconstruction review",
} as const;

export const ERROR_TYPE_LABEL = {
  internal: "Internal error",
  source_access: "Could not access source",
  source_quality: "Source quality issue",
  parseability: "Could not parse content",
} as const;
