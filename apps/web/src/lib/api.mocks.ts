import {
  type ApiErrorBody,
  type AuthResponse,
  LoginRequestSchema,
  OnboardRequestSchema,
  SignupRequestSchema,
} from "@ynara/shared-schemas";
import { HttpResponse, http } from "msw";
import { env } from "./env";

/**
 * Handlers MSW para los endpoints del backend.
 *
 * SHAPES PROVISIONALES — pendiente de acuerdo con backend.
 * Ver issue de contrato: https://github.com/BriarDevv/Ynara/issues/6
 * TODO(@BriarDevv): cuando el contrato se cierre, mirrorear estos
 * handlers contra los Pydantic finales en el mismo PR de schemas.
 *
 * Validación: usamos los Zod de `@ynara/shared-schemas` para que el
 * mock rechace lo mismo que rechazará el backend real.
 * Documentación MSW: https://mswjs.io/docs/
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

function errorResponse(body: ApiErrorBody, status: number) {
  return HttpResponse.json(body, { status });
}

export const handlers = [
  http.get(apiUrl("/v1/health"), () => HttpResponse.json({ ok: true, ts: Date.now() })),

  http.post(apiUrl("/v1/auth/signup"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = SignupRequestSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        400,
      );
    }
    const response: AuthResponse = {
      token: "mock-token-signup",
      userId: `mock-user-${Date.now()}`,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    };
    return HttpResponse.json(response);
  }),

  http.post(apiUrl("/v1/auth/login"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = LoginRequestSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        400,
      );
    }
    // Mock simple: cualquier login con shape válido pasa. Para simular
    // 401 desde devtools, cambiar este return manualmente.
    const response: AuthResponse = {
      token: "mock-token-login",
      userId: `mock-user-${Date.now()}`,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    };
    return HttpResponse.json(response);
  }),

  http.post(apiUrl("/v1/user/onboard"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = OnboardRequestSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        400,
      );
    }
    return HttpResponse.json({ ok: true, onboardedAt: Date.now() });
  }),
];
