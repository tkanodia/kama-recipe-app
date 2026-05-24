"use client";

import { useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import { createKamaApiClient } from "@kama/api-client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type KamaApiClient = ReturnType<typeof createKamaApiClient>;

export function useApiClient(): KamaApiClient {
  const { getToken } = useAuth();

  return useMemo(
    () =>
      createKamaApiClient({
        baseUrl: API_URL,
        getToken: async () => getToken(),
      }),
    [getToken],
  );
}

export { API_URL };
