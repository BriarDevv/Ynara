import { HttpResponse, http } from "msw";
import { env } from "./env";

/**
 * Handlers MSW para los endpoints del backend.
 *
 * TODO(@BriarDevv): los shapes son provisionales. Antes de mergear la PR
 * de Sesión 3 (auth real), abrir issue con @BriarDevv para acordar
 * contrato de auth (ver §4.2 del plan).
 *
 * Documentación: https://mswjs.io/docs/
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

type AuthRequest = { email: string; password: string };
type AuthResponse = { token: string; userId: string };
type OnboardRequest = {
  displayName: string;
  mood: string[];
  moodFreeText?: string;
  interestedModes: string[];
  a11y: { textSize: string; highContrast: boolean; reducedMotion: string };
};

export const handlers = [
  http.get(apiUrl("/v1/health"), () => HttpResponse.json({ ok: true, ts: Date.now() })),

  http.post(apiUrl("/v1/auth/signup"), async ({ request }) => {
    const body = (await request.json()) as AuthRequest;
    if (!body?.email || !body?.password) {
      return HttpResponse.json(
        { error: "validation", detail: "email y password requeridos" },
        { status: 400 },
      );
    }
    return HttpResponse.json<AuthResponse>({
      token: "mock-token-signup",
      userId: `mock-user-${Date.now()}`,
    });
  }),

  http.post(apiUrl("/v1/auth/login"), async ({ request }) => {
    const body = (await request.json()) as AuthRequest;
    if (!body?.email || !body?.password) {
      return HttpResponse.json(
        { error: "validation", detail: "email y password requeridos" },
        { status: 400 },
      );
    }
    return HttpResponse.json<AuthResponse>({
      token: "mock-token-login",
      userId: `mock-user-${Date.now()}`,
    });
  }),

  http.post(apiUrl("/v1/user/onboard"), async ({ request }) => {
    const body = (await request.json()) as OnboardRequest;
    if (
      !body?.displayName ||
      !Array.isArray(body?.interestedModes) ||
      body.interestedModes.length === 0
    ) {
      return HttpResponse.json(
        {
          error: "validation",
          detail: "displayName e interestedModes (mín 1) requeridos",
        },
        { status: 400 },
      );
    }
    return HttpResponse.json({ ok: true, onboardedAt: Date.now() });
  }),
];
