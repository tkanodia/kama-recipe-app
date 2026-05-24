export type JournalListResponse = {
  items: JournalEntryResponse[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type JournalEntryResponse = {
  id: string;
  canonicalRecipeId: string;
  userId: string;
  body: string;
  cookedOn?: string | null;
  tags: Array<{ id: string; name: string }>;
  media: Array<{ id: string; url: string; displayOrder: number }>;
  createdAt: string;
};

export type CreateJournalEntryRequest = {
  body: string;
  cookedOn?: string;
  tags?: Array<{ id: string; name: string }>;
  mediaRefs?: string[];
};
