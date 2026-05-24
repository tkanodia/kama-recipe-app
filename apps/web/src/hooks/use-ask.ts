"use client";

import { useCallback, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateAskSessionRequest, SendMessageRequest } from "@kama/contracts";
import { useApiClient } from "@/lib/api";
import { queryKeys } from "./query-keys";

export function useCreateAskSession() {
  const api = useApiClient();
  return useMutation({
    mutationFn: (body: CreateAskSessionRequest) => api.ask.createSession(body),
  });
}

export function useSendMessage(sessionId: string) {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SendMessageRequest) =>
      api.ask.sendMessage(sessionId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.ask.session(sessionId) });
    },
  });
}

export type StreamCallbacks = {
  onToken: (text: string) => void;
  onDone: (data: { messageId: string; citedRecipeIds: string[] }) => void;
  onError: (msg: string) => void;
};

export function useSendMessageStream(sessionId: string) {
  const qc = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (question: string, callbacks: StreamCallbacks) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(
        `${apiUrl}/api/ask/sessions/${sessionId}/messages/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
          signal: controller.signal,
        },
      );

      if (!res.ok || !res.body) {
        callbacks.onError("Failed to connect to stream");
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          try {
            const evt = JSON.parse(payload);
            if (evt.type === "token") {
              callbacks.onToken(evt.text);
            } else if (evt.type === "done") {
              callbacks.onDone({
                messageId: evt.messageId,
                citedRecipeIds: evt.citedRecipeIds,
              });
              qc.invalidateQueries({ queryKey: queryKeys.ask.session(sessionId) });
            } else if (evt.type === "error") {
              callbacks.onError(evt.text);
            }
          } catch {
            // skip malformed events
          }
        }
      }
    },
    [sessionId, qc],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { send, cancel };
}

export function useAskSession(
  sessionId: string,
  opts?: { enabled?: boolean },
) {
  const api = useApiClient();
  return useQuery({
    queryKey: queryKeys.ask.session(sessionId),
    queryFn: () => api.ask.getSession(sessionId),
    enabled: opts?.enabled ?? true,
  });
}

export function useAskSessions() {
  const api = useApiClient();
  return useQuery({
    queryKey: queryKeys.ask.sessions(),
    queryFn: () => api.ask.listSessions(),
  });
}

export function useCloseAskSession() {
  const api = useApiClient();
  return useMutation({
    mutationFn: (sessionId: string) => api.ask.closeSession(sessionId),
  });
}
