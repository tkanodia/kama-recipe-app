"use client";

import { useQuery } from "@tanstack/react-query";
import type { IngredientSearchResponse } from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useIngredientSearch(search: string, limit?: number) {
  const api = useApiClient();

  return useQuery<IngredientSearchResponse>({
    queryKey: queryKeys.ingredients.search(search),
    queryFn: () => api.ingredients.searchIngredients(search, limit),
    enabled: search.length >= 2,
  });
}
