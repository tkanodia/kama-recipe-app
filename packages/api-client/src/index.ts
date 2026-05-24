export * from "./client.js";
export * from "./ingestion.js";
export * from "./sse.js";
export * from "./recipeCandidates.js";
export * from "./recipes.js";
export * from "./drafts.js";
export * from "./journal.js";
export * from "./tags.js";
export * from "./ingredients.js";
export * from "./media.js";
export * from "./search.js";
export * from "./ask.js";
export * from "./artifacts.js";
export * from "./pantry.js";

import type { KamaClientConfig } from "./client.js";
import { createDraftsApi } from "./drafts.js";
import { createIngredientsApi } from "./ingredients.js";
import { createIngestionApi } from "./ingestion.js";
import { createJournalApi } from "./journal.js";
import { createMediaApi } from "./media.js";
import { createRecipeCandidatesApi } from "./recipeCandidates.js";
import { createRecipesApi } from "./recipes.js";
import { createSearchApi } from "./search.js";
import { createAskApi } from "./ask.js";
import { createTagsApi } from "./tags.js";
import { createArtifactsApi } from "./artifacts.js";
import { createPantryApi } from "./pantry.js";

export function createKamaApiClient(config: KamaClientConfig) {
  return {
    ingestion: createIngestionApi(config),
    recipeCandidates: createRecipeCandidatesApi(config),
    recipes: createRecipesApi(config),
    drafts: createDraftsApi(config),
    journal: createJournalApi(config),
    tags: createTagsApi(config),
    ingredients: createIngredientsApi(config),
    media: createMediaApi(config),
    search: createSearchApi(config),
    ask: createAskApi(config),
    artifacts: createArtifactsApi(config),
    pantry: createPantryApi(config),
  };
}
