export type AskMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrievedRecipeIds?: string[];
  citedRecipeIds?: string[];
  createdAt: string;
};

export type CreateAskSessionRequest = {
  question: string;
  recipeId?: string;
};

export type CreateAskSessionResponse = {
  sessionId: string;
  status: string;
  recipeId?: string | null;
  message: AskMessage;
};

export type SendMessageRequest = {
  question: string;
};

export type SendMessageResponse = {
  message: AskMessage;
};

export type AskSessionResponse = {
  sessionId: string;
  status: string;
  recipeId?: string | null;
  createdAt: string;
  lastActiveAt: string;
  messages: AskMessage[];
};

export type AskSessionListItem = {
  sessionId: string;
  status: string;
  recipeId?: string | null;
  preview: string;
  messageCount: number;
  createdAt: string;
  lastActiveAt: string;
};

export type AskSessionListResponse = {
  items: AskSessionListItem[];
};
