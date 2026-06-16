/**
 * Cliente HTTP compartido web + mobile (ADR-012). El token y la base URL se
 * inyectan vía `configureApi` para no acoplar el cliente a ningún store ni
 * runtime: la web cablea su token desde su user store, mobile desde el suyo
 * (que lee de SecureStore). Perímetro (reglas #2/#4 de AGENTS): el Bearer
 * SOLO viaja a nuestra API.
 */

type ApiConfig = {
  baseUrl: string;
  getToken: () => string | null;
  /**
   * Transporte HTTP. Default: el `fetch` global, resuelto en cada llamada (no la
   * referencia capturada) para que un parche posterior —MSW sobre el fetch global
   * en web— tome efecto. Inyectable para mock-first sin tocar los hooks: mobile
   * cablea un mock-fetch del dominio "Hoy" cuando `EXPO_PUBLIC_ENABLE_MOCKS` está
   * prendido y delega el resto (auth incluido) al fetch real. Core siempre pasa
   * una URL string ya resuelta.
   */
  fetchImpl: (input: string, init?: RequestInit) => Promise<Response>;
};

let config: ApiConfig = {
  baseUrl: "http://localhost:8080",
  getToken: () => null,
  fetchImpl: (input, init) => fetch(input, init),
};

/** Cablea base URL y token provider. Cada app lo llama una vez al cargar. */
export function configureApi(next: Partial<ApiConfig>): void {
  config = { ...config, ...next };
}

/** Base URL configurada. Útil para el cliente de streaming (SSE). */
export function getBaseUrl(): string {
  return config.baseUrl;
}

/**
 * Adjunta `Authorization: Bearer <token>` a `headers` si hay sesión y el
 * `url` apunta a NUESTRA API (perímetro reglas #2/#4: el token nunca viaja a
 * un host ajeno). SSR-safe: si `getToken` devuelve null, es no-op.
 *
 * Se exporta para que el cliente de streaming arme el mismo header con
 * `fetch` crudo sin reimplementar el guard de perímetro.
 */
export function applyAuthHeader(headers: Headers, url: string): void {
  if (headers.has("Authorization")) return;
  if (!url.startsWith(config.baseUrl)) return;
  const token = config.getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
}

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
  /**
   * Por default todo request adjunta `Authorization: Bearer <token>` si hay
   * sesión. Los endpoints públicos (login/register) pueden pasar `skipAuth`
   * para no mandarlo (igual sería no-op sin token, pero deja la intención
   * explícita).
   */
  skipAuth?: boolean;
};

async function request<T>(path: string, init: FetchInit = {}): Promise<T> {
  const url = path.startsWith("http") ? path : `${config.baseUrl}${path}`;
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  // Inyección de auth: el header se arma una sola vez en `applyAuthHeader`
  // (compartido con el cliente de streaming). Perímetro (reglas #2/#4): el
  // Bearer SOLO viaja a nuestra API. `skipAuth` lo omite explícitamente en
  // endpoints públicos (login/register).
  if (!init.skipAuth) {
    applyAuthHeader(headers, url);
  }

  const response = await config.fetchImpl(url, {
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
