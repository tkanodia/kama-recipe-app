"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useDraft(draftId: string) {
  const api = useApiClient();

  return useQuery<Record<string, unknown>>({
    queryKey: queryKeys.drafts.detail(draftId),
    queryFn: () => api.drafts.getDraft(draftId),
    enabled: !!draftId,
  });
}

export function useUpdateDraft(draftId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<Record<string, unknown>, Error, Record<string, unknown>>({
    mutationFn: (body) => api.drafts.updateDraft(draftId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.drafts.detail(draftId) });
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
    },
  });
}

export function useReviewForCanonical(draftId: string) {
  const api = useApiClient();

  return useQuery<Record<string, unknown>>({
    queryKey: queryKeys.drafts.review(draftId),
    queryFn: () => api.drafts.reviewForCanonical(draftId),
    enabled: false,
  });
}

export function useDeleteDraft(draftId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<void, Error, void>({
    mutationFn: () => api.drafts.deleteDraft(draftId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
      void qc.invalidateQueries({ queryKey: queryKeys.drafts.all });
    },
  });
}

export function usePromoteDraft(draftId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<{ canonicalRecipeId: string }, Error, void>({
    mutationFn: () => api.drafts.promote(draftId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
      void qc.invalidateQueries({ queryKey: queryKeys.drafts.all });
    },
  });
}
