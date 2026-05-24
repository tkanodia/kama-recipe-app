"use client";

import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  PatchRecipeRequest,
  RecipeDetailResponse,
  RecipeListResponse,
  RevisionListResponse,
  RestoreRevisionResponse,
  PatchRecipeResponse,
} from "@kama/contracts";
import type { ListRecipesParams } from "@kama/api-client";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useRecipes(params?: ListRecipesParams) {
  const api = useApiClient();
  return useInfiniteQuery<RecipeListResponse>({
    queryKey: queryKeys.recipes.list(params),
    queryFn: ({ pageParam }) =>
      api.recipes.listRecipes({ ...params, cursor: pageParam as string }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.nextCursor ?? undefined : undefined,
  });
}

export function useRecipe(recipeId: string, opts?: { enabled?: boolean }) {
  const api = useApiClient();
  return useQuery<RecipeDetailResponse>({
    queryKey: queryKeys.recipes.detail(recipeId),
    queryFn: () => api.recipes.getRecipe(recipeId),
    enabled: !!recipeId && (opts?.enabled ?? true),
  });
}

export function useUpdateRecipe(recipeId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<PatchRecipeResponse, Error, PatchRecipeRequest>({
    mutationFn: (body) => api.recipes.updateRecipe(recipeId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.detail(recipeId) });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.revisions(recipeId) });
    },
  });
}

export function useRecipeRevisions(recipeId: string) {
  const api = useApiClient();
  return useQuery<RevisionListResponse>({
    queryKey: queryKeys.recipes.revisions(recipeId),
    queryFn: () => api.recipes.listRevisions(recipeId),
    enabled: !!recipeId,
  });
}

export function useRestoreRevision(recipeId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<RestoreRevisionResponse, Error, string>({
    mutationFn: (revisionId) => api.recipes.restoreRevision(recipeId, revisionId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.detail(recipeId) });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.revisions(recipeId) });
    },
  });
}

export function useDeleteRecipe() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (recipeId) => {
      try {
        await api.recipes.deleteRecipe(recipeId);
      } catch {
        const baseUrl =
          process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
        const res = await fetch(
          `${baseUrl.replace(/\/$/, "")}/api/recipes/${recipeId}`,
          { method: "DELETE" },
        );
        if (!res.ok && res.status !== 204) {
          throw new Error(`Delete failed: HTTP ${res.status}`);
        }
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
    },
  });
}
