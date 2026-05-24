export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }
}

export const onRequestError = (...args: unknown[]) => {
  try {
    const Sentry = require("@sentry/nextjs");
    if (typeof Sentry.captureRequestError === "function") {
      Sentry.captureRequestError(...args);
    }
  } catch {
    // Sentry not available; ignore
  }
};
