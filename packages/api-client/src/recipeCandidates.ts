import type {
  CandidateDecisionRequest,
  CandidateDecisionResponse,
  RecipeCandidateDetail,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createRecipeCandidatesApi(config: KamaClientConfig) {
  return {
    getCandidate(candidateId: string) {
      return requestJson<RecipeCandidateDetail>(
        config,
        `/api/recipe-candidates/${candidateId}`
      );
    },
    submitDecision(candidateId: string, body: CandidateDecisionRequest) {
      return requestJson<CandidateDecisionResponse>(
        config,
        `/api/recipe-candidates/${candidateId}/decision`,
        { method: "POST", body: JSON.stringify(body) }
      );
    },
  };
}
