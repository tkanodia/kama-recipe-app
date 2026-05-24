import type { SearchRequest, SearchResponse } from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createSearchApi(config: KamaClientConfig) {
  return {
    search(body: SearchRequest) {
      return requestJson<SearchResponse>(config, "/api/search", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  };
}
