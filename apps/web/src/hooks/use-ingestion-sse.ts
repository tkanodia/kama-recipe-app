"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import type { IngestionSSEPayload } from "@kama/contracts";
import { API_URL } from "@/lib/api";

export type SSEConnectionState = "connecting" | "open" | "closed" | "error";

export function useIngestionSSE(
  jobId: string,
  onEvent: (payload: IngestionSSEPayload) => void,
) {
  const { getToken } = useAuth();
  const [connectionState, setConnectionState] =
    useState<SSEConnectionState>("connecting");
  const esRef = useRef<EventSource | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const close = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setConnectionState("closed");
  }, []);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const connect = async () => {
      const token = await getToken();
      if (cancelled) return;

      const url = new URL(
        `${API_URL.replace(/\/$/, "")}/api/ingestion/jobs/${jobId}/events`,
      );
      if (token) url.searchParams.set("token", token);

      const es = new EventSource(url.toString());
      esRef.current = es;

      es.onopen = () => {
        if (!cancelled) setConnectionState("open");
      };

      es.onerror = () => {
        if (!cancelled) setConnectionState("error");
        es.close();
      };

      es.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data) as IngestionSSEPayload;
          onEventRef.current(payload);
        } catch {
          /* ignore malformed events */
        }
      };
    };

    void connect();

    return () => {
      cancelled = true;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [jobId, getToken]);

  return { connectionState, close };
}
