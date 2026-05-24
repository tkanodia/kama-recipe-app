import type { IngestionJob } from "../domain/ingestion.js";

export type SubmitIngestionRequest = {
  sourceType: "url" | "image" | "text";
  url?: string;
  fileAssetRef?: string;
  rawTextInput?: string;
  contextNote?: string;
};

export type SubmitIngestionResponse = {
  sourceAssetId: string;
  ingestionJobId: string;
  status: "queued";
  sseUrl: string;
};

export type IngestionJobSnapshot = IngestionJob;

export type RerunIngestionResponse = {
  originalJobId: string;
  newJobId: string;
  sourceAssetId: string;
  status: "queued";
  sseUrl: string;
};

export type IngestionSSEPayload = {
  eventType: string;
  jobId: string;
  sequence: number;
  timestamp: string;
  status: string;
  internalState?: string;
  methodKey?: string;
  candidateId?: string;
  rerunAllowed?: boolean;
  errorType?: string;
  errorCode?: string;
  reasoning?: string;
};
