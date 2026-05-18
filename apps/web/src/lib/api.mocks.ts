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

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type AuthRequest = { email: string; password: string };
type AuthResponse = { token: string; userId: string };
type OnboardRequest = {
  displayName: string;
  mood: string[];
  moodFreeText?: string;
  interestedModes: string[];
  a11y: { textSize: string; highContrast: boolean; reducedMotion: string };
};

function validateAuth(body: AuthRequest | null): { ok: false; detail: string } | { ok: true } {
  if (!body) return { ok: false, detail: "body requerido" };
  if (!body.email || !EMAIL_RE.test(body.email)) return { ok: false, detail: "email inválido" };
  if (!body.password || body.password.length < 8)
    return { ok: false, detail: "password debe tener al menos 8 caracteres" };
  return { ok: true };
}

export const handlers = [
  http.get(apiUrl("/v1/health"), () => HttpResponse.json({ ok: true, ts: Date.now() })),

  http.post(apiUrl("/v1/auth/signup"), async ({ request }) => {
    const body = (await request.json().catch(() => null)) as AuthRequest | null;
    const v = validateAuth(body);
    if (!v.ok) {
      return HttpResponse.json({ error: "validation", detail: v.detail }, { status: 400 });
    }
    return HttpResponse.json<AuthResponse>({
      token: "mock-token-signup",
      userId: `mock-user-${Date.now()}`,
    });
  }),

  http.post(apiUrl("/v1/auth/login"), async ({ request }) => {
    const body = (await request.json().catch(() => null)) as AuthRequest | null;
    const v = validateAuth(body);
    if (!v.ok) {
      return HttpResponse.json({ error: "validation", detail: v.detail }, { status: 400 });
    }
    // Mock simple de credenciales: cualquier login con email/pass válido pasa.
    // Para simular 401 desde el dev panel, cambiar este return en runtime.
    return HttpResponse.json<AuthResponse>({
      token: "mock-token-login",
      userId: `mock-user-${Date.now()}`,
    });
  }),

  http.post(apiUrl("/v1/user/onboard"), async ({ request }) => {
    const body = (await request.json().catch(() => null)) as OnboardRequest | null;
    if (!body?.displayName || body.displayName.trim().length < 2) {
      return HttpResponse.json(
        { error: "validation", detail: "displayName mínimo 2 caracteres" },
        { status: 400 },
      );
    }
    if (!Array.isArray(body?.interestedModes) || body.interestedModes.length === 0) {
      return HttpResponse.json(
        { error: "validation", detail: "interestedModes mínimo 1" },
        { status: 400 },
      );
    }
    return HttpResponse.json({ ok: true, onboardedAt: Date.now() });
  }),
];
