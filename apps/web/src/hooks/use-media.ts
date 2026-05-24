"use client";

import { useMutation } from "@tanstack/react-query";
import type { PresignedUrlRequest, PresignedUrlResponse } from "@kama/contracts";
import { useApiClient } from "@/lib/api";

export function usePresignedUrl() {
  const api = useApiClient();

  return useMutation<PresignedUrlResponse, Error, PresignedUrlRequest>({
    mutationFn: (body) => api.media.getPresignedUrl(body),
  });
}
