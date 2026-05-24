import type { TagDomain } from "../enums/index.js";

export type TagResponse = {
  id: string;
  domain: TagDomain;
  name: string;
  createdBySystem: boolean;
};

export type TagListResponse = {
  items: TagResponse[];
};

export type CreateTagRequest = {
  domain: TagDomain;
  name: string;
};

export type CreateTagResponse = TagResponse & {
  created: boolean;
  createdByUserId?: string;
  createdAt?: string;
};

export type IngredientSearchItem = {
  id: string;
  name: string;
  aliases: string[];
  notes?: string | null;
};

export type IngredientSearchResponse = {
  items: IngredientSearchItem[];
};

export type CreateIngredientRequest = {
  name: string;
  aliases?: string[];
  notes?: string;
};
