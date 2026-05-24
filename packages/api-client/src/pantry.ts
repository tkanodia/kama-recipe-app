import type {
  PantryItem,
  AddPantryRequest,
  AddFromTextRequest,
  AddFromTextResponse,
  RemovePantryRequest,
  FeasibilityResponse,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createPantryApi(config: KamaClientConfig) {
  return {
    getAll() {
      return requestJson<{ items: PantryItem[] }>(config, "/api/pantry");
    },

    add(body: AddPantryRequest) {
      return requestJson<{ items: PantryItem[] }>(config, "/api/pantry", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },

    addFromText(body: AddFromTextRequest) {
      return requestJson<AddFromTextResponse>(config, "/api/pantry/from-text", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },

    remove(body: RemovePantryRequest) {
      return requestJson<void>(config, "/api/pantry", {
        method: "DELETE",
        body: JSON.stringify(body),
        parseJson: false,
      });
    },

    checkFeasibility() {
      return requestJson<FeasibilityResponse>(
        config,
        "/api/pantry/feasibility",
        { method: "POST" },
      );
    },
  };
}
