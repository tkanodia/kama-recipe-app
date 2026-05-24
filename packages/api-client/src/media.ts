import type {
  PresignedUrlRequest,
  PresignedUrlResponse,
  RegisterRecipeMediaRequest,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createMediaApi(config: KamaClientConfig) {
  return {
    getPresignedUrl(body: PresignedUrlRequest) {
      return requestJson<PresignedUrlResponse>(config, `/api/media/presigned-url`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    registerMedia(recipeId: string, body: RegisterRecipeMediaRequest) {
      return requestJson<Record<string, unknown>>(
        config,
        `/api/recipes/${recipeId}/media`,
        { method: "POST", body: JSON.stringify(body) }
      );
    },
    updateMedia(recipeId: string, mediaId: string, body: Partial<RegisterRecipeMediaRequest>) {
      return requestJson<Record<string, unknown>>(
        config,
        `/api/recipes/${recipeId}/media/${mediaId}`,
        { method: "PATCH", body: JSON.stringify(body) }
      );
    },
    deleteMedia(recipeId: string, mediaId: string) {
      return requestJson<void>(config, `/api/recipes/${recipeId}/media/${mediaId}`, {
        method: "DELETE",
        parseJson: false,
      });
    },
  };
}
