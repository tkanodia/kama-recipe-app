import type {
  CreateJournalEntryRequest,
  JournalListResponse,
  JournalEntryResponse,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createJournalApi(config: KamaClientConfig) {
  return {
    listEntries(recipeId: string, cursor?: string, limit?: number) {
      const q = new URLSearchParams();
      if (cursor) q.set("cursor", cursor);
      if (limit) q.set("limit", String(limit));
      const qs = q.toString();
      return requestJson<JournalListResponse>(
        config,
        `/api/recipes/${recipeId}/journal${qs ? `?${qs}` : ""}`
      );
    },
    createEntry(recipeId: string, body: CreateJournalEntryRequest) {
      return requestJson<JournalEntryResponse>(
        config,
        `/api/recipes/${recipeId}/journal`,
        { method: "POST", body: JSON.stringify(body) }
      );
    },
    deleteEntry(entryId: string) {
      return requestJson<void>(config, `/api/journal/${entryId}`, {
        method: "DELETE",
        parseJson: false,
      });
    },
  };
}
