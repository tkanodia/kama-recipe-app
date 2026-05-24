import type { FieldConfidence, ReviewFindingSeverity } from "../enums/index.js";

export type RecipeIngredientRow = {
  text: string;
  ingredientId?: string | null;
  quantity?: string | null;
  unit?: string | null;
  section?: string | null;
};

export type RecipeStepRow = {
  order: number;
  text: string;
  mediaRefs?: string[];
};

export type FieldProvenance = {
  sourceType: string;
  artifactId: string;
  note?: string | null;
};

export type ReviewFinding = {
  code: string;
  severity: ReviewFindingSeverity;
  field?: string | null;
  message: string;
  sourceArtifactId?: string | null;
};

export type FieldConfidenceMap = Record<string, FieldConfidence>;

export type FieldProvenanceMap = Record<string, FieldProvenance>;

export type NutritionInfo = {
  calories?: string | null;
  servingSize?: string | null;
  carbohydrates?: string | null;
  protein?: string | null;
  fat?: string | null;
  saturatedFat?: string | null;
  unsaturatedFat?: string | null;
  transFat?: string | null;
  cholesterol?: string | null;
  sodium?: string | null;
  fiber?: string | null;
  sugar?: string | null;
};

export type ChefNoteType = "tip" | "substitution" | "storage" | "variation" | "general";

export type ChefNote = {
  type: ChefNoteType;
  text: string;
};
