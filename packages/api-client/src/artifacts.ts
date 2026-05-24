import type {
  Artifact,
  ArtifactRevision,
  ArtifactListResponse,
  GenerateArtifactRequest,
} from "@kama/contracts";
import type { KamaClientConfig } from "./client.js";
import { requestJson } from "./client.js";

export function createArtifactsApi(config: KamaClientConfig) {
  return {
    generate(body: GenerateArtifactRequest) {
      return requestJson<Artifact>(config, "/api/artifacts/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },

    get(id: string) {
      return requestJson<Artifact>(config, `/api/artifacts/${id}`);
    },

    list(params?: { type?: string; status?: string }) {
      const qs = new URLSearchParams();
      if (params?.type) qs.set("type", params.type);
      if (params?.status) qs.set("status_filter", params.status);
      const q = qs.toString();
      return requestJson<ArtifactListResponse>(
        config,
        `/api/artifacts${q ? `?${q}` : ""}`,
      );
    },

    update(id: string, body: { title?: string; content?: unknown }) {
      return requestJson<Artifact>(config, `/api/artifacts/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },

    archive(id: string) {
      return requestJson<Artifact>(config, `/api/artifacts/${id}/archive`, {
        method: "POST",
      });
    },

    listRevisions(id: string) {
      return requestJson<{ items: ArtifactRevision[] }>(
        config,
        `/api/artifacts/${id}/revisions`,
      );
    },

    restoreRevision(artifactId: string, revisionId: string) {
      return requestJson<Artifact>(
        config,
        `/api/artifacts/${artifactId}/revisions/${revisionId}/restore`,
        { method: "POST" },
      );
    },
  };
}
