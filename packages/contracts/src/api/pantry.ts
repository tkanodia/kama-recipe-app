export type PantryItem = {
  id: string;
  ingredientId: string;
  ingredientName: string;
  category: string;
  addedAt: string;
};

export type AddPantryRequest = {
  ingredientIds: string[];
};

export type AddFromTextRequest = {
  text: string;
};

export type AddFromTextResponse = {
  added: PantryItem[];
  notFound: string[];
  suggestions: Array<{
    text: string;
    suggestedIngredients: Array<{ id: string; name: string }>;
  }>;
};

export type RemovePantryRequest = {
  pantryItemIds: string[];
};

export type FeasibilityRecipe = {
  recipeId: string;
  recipeTitle: string;
  feasibilityScore: number;
  totalIngredients: number;
  matchedIngredients: number;
  missingIngredients: string[];
};

export type FeasibilityResponse = {
  fullyFeasible: FeasibilityRecipe[];
  partiallyFeasible: FeasibilityRecipe[];
  notFeasible: FeasibilityRecipe[];
};
