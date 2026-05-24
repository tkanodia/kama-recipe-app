"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  JournalListResponse,
  CreateJournalEntryRequest,
  JournalEntryResponse,
} from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useJournalEntries(recipeId: string, opts?: { enabled?: boolean }) {
  const api = useApiClient();

  return useQuery<JournalListResponse>({
    queryKey: queryKeys.journal.list(recipeId),
    queryFn: () => api.journal.listEntries(recipeId),
    enabled: !!recipeId && (opts?.enabled ?? true),
  });
}

export function useCreateJournalEntry(recipeId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<JournalEntryResponse, Error, CreateJournalEntryRequest>({
    mutationFn: (body) => api.journal.createEntry(recipeId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.journal.list(recipeId) });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.detail(recipeId) });
    },
  });
}

export function useDeleteJournalEntry(recipeId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (entryId) => api.journal.deleteEntry(entryId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.journal.list(recipeId) });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.detail(recipeId) });
    },
  });
}
