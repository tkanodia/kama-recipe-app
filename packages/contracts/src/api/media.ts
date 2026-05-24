import type { MediaRole, PresignedUrlContext } from "../enums/index.js";

export type PresignedUrlRequest = {
  fileName: string;
  contentType: string;
  context: PresignedUrlContext;
};

export type PresignedUrlResponse = {
  uploadUrl: string;
  assetRef: string;
  expiresAt: string;
};

export type RegisterRecipeMediaRequest = {
  assetRef: string;
  role: MediaRole;
  displayOrder?: number;
};
