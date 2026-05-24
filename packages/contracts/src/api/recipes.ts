import type { ChefNote, NutritionInfo, RecipeIngredientRow, RecipeStepRow } from "../domain/common.js";

import type { ParsedQueryResponse } from "./search.js";

export type RecipeListItem = {
  id: string;
  kind: "canonical" | "draft";
  title: string;
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  heroImageUrl?: string | null;
  recipeTags: Array<{ id: string; name: string }>;
  journalEntryCount?: number;
  feasibilityStatus?: "fully_feasible" | "partially_feasible" | "not_feasible" | null;
  updatedAt: string;
};

export type RecipeListResponse = {
  items: RecipeListItem[];
  nextCursor: string | null;
  hasMore: boolean;
  parsedQuery?: ParsedQueryResponse | null;
  searchQualityReduced?: boolean;
};

export type RecipeDetailResponse = {
  id: string;
  title: string;
  description?: string | null;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: Array<{ id: string; name: string }>;
  heroImage?: { id: string; assetRef: string } | null;
  sourceUrl?: string | null;
  sourceType?: string | null;
  nutrition?: NutritionInfo | null;
  notes?: ChefNote[];
  howToServe?: string | null;
  journalSummary?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type PatchRecipeRequest = {
  title?: string;
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  ingredients?: RecipeIngredientRow[];
  steps?: RecipeStepRow[];
  recipeTags?: string[];
  nutrition?: NutritionInfo | null;
  notes?: ChefNote[];
  howToServe?: string | null;
};

export type PatchRecipeResponse = {
  id: string;
  revisionCreated: boolean;
  revisionId?: string;
  updatedAt: string;
};

export type RevisionListItem = {
  id: string;
  canonicalRecipeId: string;
  changeSummary?: string | null;
  createdAt: string;
};

export type RevisionListResponse = {
  items: RevisionListItem[];
};

export type RestoreRevisionResponse = {
  recipeId: string;
  restoredFromRevisionId: string;
  newRevisionId: string;
  updatedAt: string;
};
