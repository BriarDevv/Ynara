import { env } from "./env";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type FetchInit = Omit<RequestInit, "body"> & {
  /** El body se serializa a JSON automáticamente. */
  body?: unknown;
};

async function request<T>(path: string, init: FetchInit = {}): Promise<T> {
  const url = path.startsWith("http") ? path : `${env.NEXT_PUBLIC_API_URL}${path}`;
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(url, {
    ...init,
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  const isJson = response.headers.get("Content-Type")?.toLowerCase().includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    throw new ApiError(response.status, payload);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, init?: Omit<FetchInit, "body" | "method">) =>
    request<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init?: Omit<FetchInit, "body" | "method">) =>
    request<T>(path, { ...init, method: "POST", body }),
  put: <T>(path: string, body?: unknown, init?: Omit<FetchInit, "body" | "method">) =>
    request<T>(path, { ...init, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, init?: Omit<FetchInit, "body" | "method">) =>
    request<T>(path, { ...init, method: "PATCH", body }),
  delete: <T>(path: string, init?: Omit<FetchInit, "body" | "method">) =>
    request<T>(path, { ...init, method: "DELETE" }),
};
