"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import type { SearchRequest, SearchResponse } from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useSearch(
  query: string,
  filters?: SearchRequest["filters"],
  opts?: { enabled?: boolean }
) {
  const api = useApiClient();

  return useInfiniteQuery<SearchResponse>({
    queryKey: queryKeys.search.results(query, filters as Record<string, unknown>),
    queryFn: async ({ pageParam }) => {
      return api.search.search({
        query: query || undefined,
        filters,
        limit: 20,
        cursor: (pageParam as number) ?? 0,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
    enabled: (opts?.enabled ?? true) && (!!query || !!filters),
  });
}
