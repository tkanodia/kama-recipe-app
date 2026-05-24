export type ShoppingListItem = {
  text: string;
  quantity?: string;
  unit?: string;
  ingredientName?: string;
  recipeId?: string | null;
  recipeTitle?: string | null;
  checked?: boolean;
};

export type ShoppingListCategory = {
  category: string;
  items: ShoppingListItem[];
};

export type ShoppingListContent = {
  categories: ShoppingListCategory[];
  recipeCount: number;
};

export type MealPlanSlot = {
  meal: string;
  recipeId?: string | null;
  recipeTitle?: string;
  notes?: string;
};

export type MealPlanDay = {
  day: number;
  label: string;
  slots: MealPlanSlot[];
};

export type MealPlanContent = {
  days: MealPlanDay[];
  mealsPerDay: number;
};

export type Artifact = {
  id: string;
  artifactType: "shopping_list" | "meal_plan" | "pantry_feasibility";
  title: string;
  content: ShoppingListContent | MealPlanContent | Record<string, unknown>;
  sourceRecipeIds: string[];
  status: "active" | "archived";
  createdAt: string;
  updatedAt: string;
};

export type ArtifactRevision = {
  id: string;
  artifactId: string;
  snapshotPayload: Record<string, unknown>;
  changeSummary?: string | null;
  createdAt: string;
};

export type GenerateArtifactRequest = {
  artifactType: string;
  recipeIds?: string[];
  title?: string;
  instructions?: string;
  days?: number;
  mealsPerDay?: number;
};

export type ArtifactListResponse = {
  items: Artifact[];
  total: number;
};
