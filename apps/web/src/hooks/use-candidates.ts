"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  RecipeCandidateDetail,
  CandidateDecisionRequest,
  CandidateDecisionResponse,
} from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useCandidate(candidateId: string) {
  const api = useApiClient();

  return useQuery<RecipeCandidateDetail>({
    queryKey: queryKeys.candidates.detail(candidateId),
    queryFn: () => api.recipeCandidates.getCandidate(candidateId),
    enabled: !!candidateId,
  });
}

export function useCandidateDecision(candidateId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<CandidateDecisionResponse, Error, CandidateDecisionRequest>({
    mutationFn: (body) => api.recipeCandidates.submitDecision(candidateId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.recipes.all });
      void qc.invalidateQueries({ queryKey: queryKeys.drafts.all });
    },
  });
}
