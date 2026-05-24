import type { TagDomain } from "../enums/index.js";

export type Ingredient = {
  id: string;
  name: string;
  aliases: string[];
  notes?: string | null;
  createdAt: string;
};

export type Tag = {
  id: string;
  domain: TagDomain;
  name: string;
  createdBySystem: boolean;
  createdByUserId?: string | null;
  createdAt: string;
};

export type CookJournalEntry = {
  id: string;
  canonicalRecipeId: string;
  userId: string;
  body: string;
  cookedOn?: string | null;
  tags: string[];
  createdAt: string;
};

export type JournalEntryMedia = {
  id: string;
  journalEntryId: string;
  assetRef: string;
  source: string;
  displayOrder?: number | null;
  createdAt: string;
};
