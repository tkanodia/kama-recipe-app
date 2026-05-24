import type {
  PatchRecipeRequest,
  PatchRecipeResponse,
  RecipeDetailResponse,
  RecipeListResponse,
  RestoreRevisionResponse,
  RevisionListResponse,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export type ListRecipesParams = Record<string, string | number | undefined>;

export function createRecipesApi(config: KamaClientConfig) {
  return {
    listRecipes(params?: ListRecipesParams) {
      const q = new URLSearchParams();
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          if (v !== undefined) q.set(k, String(v));
        }
      }
      const qs = q.toString();
      return requestJson<RecipeListResponse>(
        config,
        `/api/recipes${qs ? `?${qs}` : ""}`
      );
    },
    getRecipe(recipeId: string) {
      return requestJson<RecipeDetailResponse>(config, `/api/recipes/${recipeId}`);
    },
    updateRecipe(recipeId: string, body: PatchRecipeRequest) {
      return requestJson<PatchRecipeResponse>(config, `/api/recipes/${recipeId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    listRevisions(recipeId: string) {
      return requestJson<RevisionListResponse>(
        config,
        `/api/recipes/${recipeId}/revisions`
      );
    },
    restoreRevision(recipeId: string, revisionId: string) {
      return requestJson<RestoreRevisionResponse>(
        config,
        `/api/recipes/${recipeId}/revisions/${revisionId}/restore`,
        { method: "POST" }
      );
    },
    deleteRecipe(recipeId: string) {
      return requestJson<void>(config, `/api/recipes/${recipeId}`, {
        method: "DELETE",
      });
    },
  };
}
