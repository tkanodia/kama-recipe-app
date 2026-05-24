import type { MediaRole, ReviewMode } from "../enums/index.js";
import type {
  FieldConfidenceMap,
  FieldProvenanceMap,
  RecipeIngredientRow,
  RecipeStepRow,
  ReviewFinding,
} from "./common.js";

export type RecipeCandidate = {
  id: string;
  sourceAssetId: string;
  ingestionJobId: string;
  title: string;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: string[];
  canonicalEligible: boolean;
  draftEligible: boolean;
  reviewMode: ReviewMode;
  reviewFindings: ReviewFinding[];
  fieldConfidenceMap: FieldConfidenceMap;
  selectedExtractionMethod: string;
  sourceArtifactIds: string[];
  fieldProvenanceMap: FieldProvenanceMap;
  createdAt: string;
};

export type DraftRecipe = {
  id: string;
  userId: string;
  originSourceAssetId: string;
  originRecipeCandidateId: string;
  title: string;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: string[];
  promotionEligible: boolean;
  createdAt: string;
  updatedAt: string;
};

export type CanonicalRecipe = {
  id: string;
  userId: string;
  title: string;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: string[];
  heroImageId?: string | null;
  journalSummary?: string | null;
  fieldProvenanceMap: FieldProvenanceMap;
  sourceAssetId?: string | null;
  originRecipeCandidateId?: string | null;
  promotedFromDraft: boolean;
  promotedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type RecipeRevision = {
  id: string;
  canonicalRecipeId: string;
  snapshotPayload: Record<string, unknown>;
  changeSummary?: string | null;
  createdAt: string;
};

export type RecipeMedia = {
  id: string;
  canonicalRecipeId: string;
  mediaType: "image";
  role: MediaRole;
  source: "extracted" | "uploaded";
  assetRef: string;
  displayOrder?: number | null;
  createdAt: string;
};
