"use client";

import {
  useQuery,
  useMutation,
} from "@tanstack/react-query";
import type {
  SubmitIngestionRequest,
  SubmitIngestionResponse,
  IngestionJobSnapshot,
  RerunIngestionResponse,
} from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useSubmitIngestion() {
  const api = useApiClient();

  return useMutation<SubmitIngestionResponse, Error, SubmitIngestionRequest>({
    mutationFn: (body) => api.ingestion.submitSource(body),
  });
}

export function useIngestionJob(jobId: string, enabled = true) {
  const api = useApiClient();

  return useQuery<IngestionJobSnapshot>({
    queryKey: queryKeys.ingestion.job(jobId),
    queryFn: () => api.ingestion.getJobStatus(jobId),
    enabled: !!jobId && enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      const terminal = ["review_ready", "draft_ready", "failed", "unsupported"];
      if (terminal.includes(data.status)) return false;
      return 3000;
    },
  });
}

export function useRerunJob() {
  const api = useApiClient();

  return useMutation<RerunIngestionResponse, Error, string>({
    mutationFn: (jobId) => api.ingestion.rerunJob(jobId),
  });
}
