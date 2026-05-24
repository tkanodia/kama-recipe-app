import type {
  IngestionJobSnapshot,
  RerunIngestionResponse,
  SubmitIngestionRequest,
  SubmitIngestionResponse,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createIngestionApi(config: KamaClientConfig) {
  return {
    submitSource(body: SubmitIngestionRequest) {
      return requestJson<SubmitIngestionResponse>(config, "/api/ingestion", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    getJobStatus(jobId: string) {
      return requestJson<IngestionJobSnapshot>(config, `/api/ingestion/jobs/${jobId}`);
    },
    rerunJob(jobId: string) {
      return requestJson<RerunIngestionResponse>(
        config,
        `/api/ingestion/jobs/${jobId}/rerun`,
        { method: "POST" }
      );
    },
  };
}
