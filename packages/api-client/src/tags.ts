import type { CreateTagRequest, CreateTagResponse, TagListResponse } from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createTagsApi(config: KamaClientConfig) {
  return {
    listTags(domain: "recipe" | "journal", search?: string) {
      const q = new URLSearchParams({ domain });
      if (search) q.set("search", search);
      return requestJson<TagListResponse>(config, `/api/tags?${q.toString()}`);
    },
    createOrReuseTag(body: CreateTagRequest) {
      return requestJson<CreateTagResponse>(config, `/api/tags`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  };
}
