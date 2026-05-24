import type {
  FieldConfidenceMap,
  FieldProvenanceMap,
  RecipeIngredientRow,
  RecipeStepRow,
  ReviewFinding,
} from "../domain/common.js";
import type { ReviewMode } from "../enums/index.js";

export type RecipeCandidateDetail = {
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
  fieldProvenanceMap: FieldProvenanceMap;
  selectedExtractionMethod: string;
  sourceArtifactIds: string[];
  previewImageUrl?: string | null;
  sourceContext?: Record<string, unknown>;
  allowedActions?: {
    canSaveCanonical: boolean;
    canSaveDraft: boolean;
    canDiscard: boolean;
  };
  reviewAgentSummary?: Record<string, unknown>;
  createdAt: string;
};

export type CandidateDecisionAction = "save_canonical" | "save_draft" | "discard";

export type CandidateDecisionRequest = {
  action: CandidateDecisionAction;
  editedFields?: Record<string, unknown>;
};

export type CandidateDecisionResponse = {
  canonicalRecipeId?: string;
  draftRecipeId?: string;
  discarded?: boolean;
};
