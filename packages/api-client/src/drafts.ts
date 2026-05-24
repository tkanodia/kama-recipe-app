import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createDraftsApi(config: KamaClientConfig) {
  return {
    getDraft(draftId: string) {
      return requestJson<Record<string, unknown>>(config, `/api/drafts/${draftId}`);
    },
    updateDraft(draftId: string, body: Record<string, unknown>) {
      return requestJson<Record<string, unknown>>(config, `/api/drafts/${draftId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    deleteDraft(draftId: string) {
      return requestJson<void>(config, `/api/drafts/${draftId}`, {
        method: "DELETE",
        parseJson: false,
      });
    },
    reviewForCanonical(draftId: string) {
      return requestJson<Record<string, unknown>>(
        config,
        `/api/drafts/${draftId}/review-for-canonical`,
        { method: "POST" }
      );
    },
    promote(draftId: string) {
      return requestJson<{ canonicalRecipeId: string }>(
        config,
        `/api/drafts/${draftId}/promote`,
        { method: "POST" }
      );
    },
  };
}
