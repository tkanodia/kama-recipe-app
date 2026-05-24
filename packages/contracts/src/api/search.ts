export type SearchFilters = {
  tagIds?: string[];
  ingredientIds?: string[];
  maxCookTimeMinutes?: number;
  maxPrepTimeMinutes?: number;
  minServings?: number;
  maxServings?: number;
};

export type SearchRequest = {
  query?: string;
  filters?: SearchFilters;
  limit?: number;
  cursor?: number;
};

export type SearchResultItem = {
  id: string;
  title: string;
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  heroImageUrl?: string | null;
  recipeTags: Array<{ id: string; name: string }>;
  relevanceScore: number;
  matchReasons: string[];
  createdAt: string;
  updatedAt: string;
};

export type ParsedQueryResponse = {
  semanticQuery: string;
  queryIntent: "search" | "ask" | "ambiguous";
  tagIds: string[];
  ingredientIds: string[];
};

export type SearchResponse = {
  items: SearchResultItem[];
  parsedQuery: ParsedQueryResponse;
  nextCursor: number | null;
  hasMore: boolean;
  searchQualityReduced: boolean;
};
