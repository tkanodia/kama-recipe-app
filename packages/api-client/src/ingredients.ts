import type {
  CreateIngredientRequest,
  IngredientSearchResponse,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createIngredientsApi(config: KamaClientConfig) {
  return {
    searchIngredients(search: string, limit?: number) {
      const q = new URLSearchParams({ search });
      if (limit) q.set("limit", String(limit));
      return requestJson<IngredientSearchResponse>(
        config,
        `/api/ingredients?${q.toString()}`
      );
    },
    createIngredient(body: CreateIngredientRequest) {
      return requestJson<Record<string, unknown>>(config, `/api/ingredients`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  };
}
