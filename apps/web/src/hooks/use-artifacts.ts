"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  Artifact,
  ArtifactRevision,
  ArtifactListResponse,
  GenerateArtifactRequest,
} from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useGenerateArtifact() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<Artifact, Error, GenerateArtifactRequest>({
    mutationFn: (body) => api.artifacts.generate(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.artifacts.all });
    },
  });
}

export function useArtifact(id: string, opts?: { enabled?: boolean }) {
  const api = useApiClient();

  return useQuery<Artifact>({
    queryKey: queryKeys.artifacts.detail(id),
    queryFn: () => api.artifacts.get(id),
    enabled: !!id && (opts?.enabled ?? true),
  });
}

export function useArtifactsList(params?: {
  type?: string;
  status?: string;
}) {
  const api = useApiClient();

  const keyParams: Record<string, string | undefined> = {
    type: params?.type,
    status: params?.status,
  };

  return useQuery<ArtifactListResponse>({
    queryKey: queryKeys.artifacts.list(keyParams),
    queryFn: () => api.artifacts.list(params),
  });
}

export function useUpdateArtifact(id: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<
    Artifact,
    Error,
    { title?: string; content?: unknown }
  >({
    mutationFn: (body) => api.artifacts.update(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.artifacts.detail(id) });
      void qc.invalidateQueries({ queryKey: queryKeys.artifacts.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.artifacts.revisions(id),
      });
    },
  });
}

export function useArchiveArtifact() {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<Artifact, Error, string>({
    mutationFn: (id) => api.artifacts.archive(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.artifacts.all });
    },
  });
}

export function useArtifactRevisions(
  id: string,
  opts?: { enabled?: boolean },
) {
  const api = useApiClient();

  return useQuery<{ items: ArtifactRevision[] }>({
    queryKey: queryKeys.artifacts.revisions(id),
    queryFn: () => api.artifacts.listRevisions(id),
    enabled: !!id && (opts?.enabled ?? true),
  });
}

export function useRestoreArtifactRevision(artifactId: string) {
  const api = useApiClient();
  const qc = useQueryClient();

  return useMutation<Artifact, Error, string>({
    mutationFn: (revisionId) =>
      api.artifacts.restoreRevision(artifactId, revisionId),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: queryKeys.artifacts.detail(artifactId),
      });
      void qc.invalidateQueries({ queryKey: queryKeys.artifacts.all });
      void qc.invalidateQueries({
        queryKey: queryKeys.artifacts.revisions(artifactId),
      });
    },
  });
}
