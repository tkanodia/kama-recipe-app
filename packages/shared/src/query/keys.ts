export const recipeKeys = {
  all: ["recipes"] as const,
  list: (filters?: Record<string, unknown>) => [...recipeKeys.all, "list", filters] as const,
  detail: (id: string) => [...recipeKeys.all, "detail", id] as const,
  revisions: (id: string) => [...recipeKeys.all, "revisions", id] as const,
};

export const jobKeys = {
  all: ["ingestion-jobs"] as const,
  detail: (jobId: string) => [...jobKeys.all, jobId] as const,
};

export const candidateKeys = {
  all: ["candidates"] as const,
  detail: (id: string) => [...candidateKeys.all, id] as const,
};

export const tagKeys = {
  all: ["tags"] as const,
  domain: (domain: string) => [...tagKeys.all, domain] as const,
};

export const journalKeys = {
  recipe: (recipeId: string) => ["journal", recipeId] as const,
};

export const draftKeys = {
  detail: (id: string) => ["drafts", id] as const,
};
