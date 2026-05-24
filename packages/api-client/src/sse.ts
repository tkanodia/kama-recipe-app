import type { IngestionSSEPayload } from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";

export type SSEHandlers = {
  onEvent?: (payload: IngestionSSEPayload) => void;
  onError?: (err: Error) => void;
  onOpen?: () => void;
};

/**
 * Subscribe to ingestion job SSE. On disconnect, callers should refetch job snapshot via getJobStatus.
 */
export function subscribeIngestionJobEvents(
  config: KamaClientConfig,
  jobId: string,
  handlers: SSEHandlers
): { close: () => void } {
  let closed = false;
  let es: EventSource | null = null;

  const run = async () => {
    const token = await config.getToken();
    const url = new URL(
      `${config.baseUrl.replace(/\/$/, "")}/api/ingestion/jobs/${jobId}/events`
    );
    if (token) {
      url.searchParams.set("token", token);
    }
    es = new EventSource(url.toString());
    es.onopen = () => handlers.onOpen?.();
    es.onerror = (e) => {
      if (!closed) handlers.onError?.(new Error("SSE connection error"));
      es?.close();
    };
    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data) as IngestionSSEPayload;
        handlers.onEvent?.(payload);
      } catch {
        /* ignore */
      }
    };
  };

  void run();

  return {
    close: () => {
      closed = true;
      es?.close();
    },
  };
}
