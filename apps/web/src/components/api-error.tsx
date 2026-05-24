"use client";

import { ApiError } from "@kama/api-client";

const ERROR_MESSAGES: Record<string, string> = {
  source_access:
    "We couldn't access that source. Please check the URL and try again.",
  source_quality:
    "The source didn't contain enough information to extract a recipe.",
  parseability: "We couldn't identify a recipe in that content.",
  not_found: "The item you were looking for could not be found.",
  validation_error: "Some of the information provided is invalid.",
  rate_limited: "You're making requests too quickly. Please wait a moment.",
  unauthorized: "Please sign in to continue.",
  forbidden: "You don't have permission to do that.",
  internal: "Something went wrong on our end. Please try again.",
};

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body) {
    const body = error.body as { error?: { code?: string; message?: string } };
    const code = body?.error?.code;
    if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
    if (body?.error?.message) return body.error.message;
  }
  if (error instanceof Error) return error.message;
  return ERROR_MESSAGES.internal;
}

type ApiErrorDisplayProps = {
  error: unknown;
  onRetry?: () => void;
  className?: string;
};

export function ApiErrorDisplay({
  error,
  onRetry,
  className = "",
}: ApiErrorDisplayProps) {
  const message = getErrorMessage(error);

  return (
    <div
      className={`rounded-lg border border-red-800/40 bg-red-950/30 p-4 text-center ${className}`}
    >
      <p className="text-sm text-red-300">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md bg-orange-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-orange-500 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  );
}
