import type {
  ErrorType,
  InternalState,
  JobStatus,
  ReviewMode,
  ExtractionMethodStatus,
  ConfidenceLevel,
} from "../enums/index.js";

export type ExtractionMethodPlanEntry = {
  methodKey: string;
  priority: number;
  feasible: boolean;
  feasibilityReason?: string;
  requiredArtifacts: string[];
  addedBy?: "initial_plan" | "agent_reasoning";
  status: ExtractionMethodStatus;
  startedAt?: string | null;
  completedAt?: string | null;
  outputSummary?: {
    candidateCreated: boolean;
    canonicalEligible: boolean;
    draftEligible: boolean;
    confidenceLevel?: ConfidenceLevel;
    notes?: string[];
  } | null;
  failure?: {
    errorType?: ErrorType;
    errorCode?: string;
    message?: string;
  } | null;
  stopDecision?: {
    stopPipeline: boolean;
    reason?: string;
  } | null;
  agentDecision?: {
    reasoning: string;
    alternativesConsidered: string[];
    deterministic: boolean;
  } | null;
};

export type IngestionJobHistoryEvent = {
  eventType: string;
  timestamp: string;
  internalState?: string;
  methodKey?: string;
  status?: string;
  internalErrorState?: string;
  reasoning?: string;
  notes?: string[];
};

export type SourceAsset = {
  id: string;
  userId: string;
  sourceType: "url" | "image" | "text";
  originalUrl?: string | null;
  rawTextInput?: string | null;
  fileAssetRef?: string | null;
  contextNote?: string | null;
  createdAt: string;
};

export type IngestionJob = {
  id: string;
  sourceAssetId: string;
  status: JobStatus;
  internalState: InternalState;
  internalErrorState?: string | null;
  processorFamily: string;
  processorVariant?: string | null;
  reviewMode?: ReviewMode | null;
  candidateId?: string | null;
  normalizedArtifactIds: string[];
  errorType?: ErrorType | null;
  errorCode?: string | null;
  rerunAllowed: boolean;
  userRecoverable: boolean;
  extractionPlan: ExtractionMethodPlanEntry[];
  stateHistory: IngestionJobHistoryEvent[];
  metadata?: Record<string, unknown>;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  updatedAt: string;
  lastHeartbeatAt?: string | null;
};
