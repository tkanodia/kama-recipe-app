"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  TagListResponse,
  CreateTagRequest,
  CreateTagResponse,
} from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useTags(domain: "recipe" | "journal", search?: string) {
  const api = useApiClient();

  return useQuery<TagListResponse>({
    queryKey: queryKeys.tags.byDomain(domain, search),
    queryFn: () => api.tags.listTags(domain, search),
  });
}

export function useCreateTag() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<CreateTagResponse, Error, CreateTagRequest>({
    mutationFn: (body) => api.tags.createOrReuseTag(body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({
        queryKey: queryKeys.tags.byDomain(variables.domain),
      });
    },
  });
}
