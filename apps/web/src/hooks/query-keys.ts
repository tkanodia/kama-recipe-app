export const queryKeys = {
  recipes: {
    all: ["recipes"] as const,
    list: (params?: Record<string, string | number | undefined>) =>
      ["recipes", "list", params ?? {}] as const,
    detail: (id: string) => ["recipes", id] as const,
    revisions: (id: string) => ["recipes", id, "revisions"] as const,
  },
  ingestion: {
    job: (jobId: string) => ["ingestion", "jobs", jobId] as const,
  },
  candidates: {
    detail: (id: string) => ["candidates", id] as const,
  },
  drafts: {
    all: ["drafts"] as const,
    detail: (id: string) => ["drafts", id] as const,
    review: (id: string) => ["drafts", id, "review"] as const,
  },
  ingredients: {
    search: (query: string) => ["ingredients", "search", query] as const,
  },
  tags: {
    byDomain: (domain: "recipe" | "journal", search?: string) =>
      ["tags", domain, search ?? ""] as const,
  },
  journal: {
    list: (recipeId: string) => ["journal", recipeId] as const,
  },
  search: {
    all: ["search"] as const,
    results: (query: string, filters?: Record<string, unknown>) =>
      ["search", query, filters ?? {}] as const,
  },
  ask: {
    all: ["ask"] as const,
    sessions: () => ["ask", "sessions"] as const,
    session: (sessionId: string) => ["ask", sessionId] as const,
  },
  artifacts: {
    all: ["artifacts"] as const,
    list: (params?: Record<string, string | undefined>) =>
      ["artifacts", "list", params ?? {}] as const,
    detail: (id: string) => ["artifacts", id] as const,
    revisions: (id: string) => ["artifacts", id, "revisions"] as const,
  },
  pantry: {
    all: ["pantry"] as const,
    list: () => ["pantry", "list"] as const,
    feasibility: () => ["pantry", "feasibility"] as const,
  },
} as const;
