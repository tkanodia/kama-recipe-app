"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  PantryItem,
  AddPantryRequest,
  AddFromTextRequest,
  AddFromTextResponse,
  FeasibilityResponse,
} from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function usePantryItems() {
  const api = useApiClient();

  return useQuery<{ items: PantryItem[] }>({
    queryKey: queryKeys.pantry.list(),
    queryFn: () => api.pantry.getAll(),
  });
}

export function useAddPantry() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<{ items: PantryItem[] }, Error, AddPantryRequest>({
    mutationFn: (body) => api.pantry.add(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.pantry.all });
    },
  });
}

export function useAddPantryFromText() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<AddFromTextResponse, Error, AddFromTextRequest>({
    mutationFn: (body) => api.pantry.addFromText(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.pantry.all });
    },
  });
}

export function useRemovePantry() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<void, Error, string[]>({
    mutationFn: (pantryItemIds) => api.pantry.remove({ pantryItemIds }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.pantry.all });
    },
  });
}

export function useFeasibility(opts?: { enabled?: boolean }) {
  const api = useApiClient();

  return useQuery<FeasibilityResponse>({
    queryKey: queryKeys.pantry.feasibility(),
    queryFn: () => api.pantry.checkFeasibility(),
    enabled: opts?.enabled ?? true,
  });
}
