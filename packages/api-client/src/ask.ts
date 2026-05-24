import type {
  CreateAskSessionRequest,
  CreateAskSessionResponse,
  SendMessageRequest,
  SendMessageResponse,
  AskSessionResponse,
  AskSessionListResponse,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createAskApi(config: KamaClientConfig) {
  return {
    createSession(body: CreateAskSessionRequest) {
      return requestJson<CreateAskSessionResponse>(config, "/api/ask/sessions", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    sendMessage(sessionId: string, body: SendMessageRequest) {
      return requestJson<SendMessageResponse>(
        config,
        `/api/ask/sessions/${sessionId}/messages`,
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      );
    },
    closeSession(sessionId: string) {
      return requestJson<{ sessionId: string; status: string }>(
        config,
        `/api/ask/sessions/${sessionId}/close`,
        { method: "POST" },
      );
    },
    getSession(sessionId: string) {
      return requestJson<AskSessionResponse>(
        config,
        `/api/ask/sessions/${sessionId}`,
      );
    },
    listSessions() {
      return requestJson<AskSessionListResponse>(
        config,
        "/api/ask/sessions",
      );
    },
  };
}
