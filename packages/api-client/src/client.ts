export type KamaClientConfig = {
  baseUrl: string;
  getToken: () => Promise<string | null>;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function requestJson<T>(
  config: KamaClientConfig,
  path: string,
  init: RequestInit & { parseJson?: boolean } = {}
): Promise<T> {
  const { parseJson = true, ...rest } = init;
  const token = await config.getToken();
  const headers = new Headers(rest.headers);
  if (!headers.has("Content-Type") && rest.body && typeof rest.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${config.baseUrl.replace(/\/$/, "")}${path}`, {
    ...rest,
    headers,
  });
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(`HTTP ${res.status}`, res.status, body);
  }
  if (res.status === 204 || !parseJson) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
