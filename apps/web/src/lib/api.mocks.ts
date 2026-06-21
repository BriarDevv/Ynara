import {
  type ApiErrorBody,
  type AuthResponse,
  ChatRequestSchema,
  type ChatResponse,
  LoginRequestSchema,
  OnboardRequestSchema,
  SignupRequestSchema,
} from "@ynara/shared-schemas";
import { HttpResponse, http } from "msw";
import { agendaHandlers } from "@/features/agenda/mocks";
import { cannedActions, cannedReply, isAgentMode } from "@/features/chat/constants";
import { memoryHandlers } from "@/features/memory/mocks";
import { profileHandlers } from "@/features/profile/mocks";
import { todayHandlers } from "@/features/today/mocks";
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

  // ALIAS TEMPORAL del contrato PROVISIONAL camelCase (@ynara/shared-schemas:
  // {token, userId}). La web YA NO los usa (migró a register/token de core);
  // se dejan hasta retirar shared-schemas/auth. Ver BriarDevv/Ynara#6.
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

  // Contrato REAL de auth (mirror de los Pydantic de apps/backend, rutas
  // /v1/auth/*). El AuthStep de la web usa signUp/logIn de @ynara/core, que
  // pegan a /register THEN /token (signup) y /token + /me (login). Estos
  // handlers espejan ese contrato para que dev-con-mocks siga andando.
  //
  // POST /v1/auth/register -> UserOut (SIN token; el token se pide aparte).
  http.post(apiUrl("/v1/auth/register"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = SignupRequestSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      // El backend (FastAPI) responde 422 a validación de request.
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        422,
      );
    }
    const now = new Date().toISOString();
    // Shape de UserOut (snake_case) que parsea AuthUserSchema de core.
    return HttpResponse.json(
      {
        id: `mock-user-${Date.now()}`,
        email: parsed.data.email,
        display_name: null,
        is_ephemeral: false,
        onboarding_completed: false,
        retention_sensitive_days: 180,
        created_at: now,
        updated_at: now,
      },
      { status: 201 },
    );
  }),

  // POST /v1/auth/token -> TokenOut (access + refresh, snake_case). Cualquier
  // par con shape válido pasa; para simular 401 cambiar este return a mano.
  http.post(apiUrl("/v1/auth/token"), async ({ request }) => {
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
        422,
      );
    }
    // Shape de TokenOut que parsea TokenResponseSchema de core. El
    // refresh_token se devuelve poblado aunque la web hoy lo descarte.
    return HttpResponse.json({
      access_token: `mock-token-${Date.now()}`,
      token_type: "bearer",
      refresh_token: `mock-refresh-${Date.now()}`,
    });
  }),

  // GET /v1/auth/me -> UserOut. logIn de core lo llama (con el Bearer del
  // token recién emitido) para resolver el userId. Sin este handler el login
  // con mocks daría 404 tras /token.
  http.get(apiUrl("/v1/auth/me"), () => {
    const now = new Date().toISOString();
    return HttpResponse.json({
      id: `mock-user-${Date.now()}`,
      email: "mock@ynara.app",
      display_name: null,
      is_ephemeral: false,
      onboarding_completed: false,
      retention_sensitive_days: 180,
      created_at: now,
      updated_at: now,
    });
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

  // POST /v1/chat (no-streaming). El streaming va aparte en /v1/chat/stream (W3).
  // Respuesta canned por modo; `actions` solo en modos Qwen (productividad,
  // memoria). El backend real es M9 — esto espeja el contrato cerrado en #61.
  http.post(apiUrl("/v1/chat"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = ChatRequestSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      // El backend (FastAPI) responde 422 a validación de request.
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        422,
      );
    }

    const { text, mode, session_id } = parsed.data;
    const response: ChatResponse = {
      text: cannedReply(mode, text),
      actions: isAgentMode(mode) ? cannedActions(mode) : [],
      session_id: session_id ?? crypto.randomUUID(),
      finish_reason: "stop",
    };
    return HttpResponse.json(response);
  }),

  // POST /v1/chat/stream (streaming SSE, W3). Pseudo-streamea la misma
  // respuesta canned del handler no-streaming, pero token a token: parte el
  // texto en ventanas chicas (~6 chars) emitidas como eventos `token`, y
  // cierra con un evento `done` (con `actions` solo en modos Qwen). El wire
  // sigue el contrato cerrado en #61 que consume `createSseParser` (sse.ts).
  http.post(apiUrl("/v1/chat/stream"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = ChatRequestSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      // El backend (FastAPI) responde 422 a validación de request, igual que
      // el handler no-streaming.
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        422,
      );
    }

    const { text, mode, session_id } = parsed.data;
    const reply = cannedReply(mode, text);
    const sessionId = session_id ?? crypto.randomUUID();
    const actions = isAgentMode(mode) ? cannedActions(mode) : [];

    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        // Ventanas fijas de 6 chars: determinista (no usa timers ni random),
        // así si estos handlers se reusan en tests el output es estable.
        const WINDOW = 6;
        for (let i = 0; i < reply.length; i += WINDOW) {
          const delta = reply.slice(i, i + WINDOW);
          controller.enqueue(
            encoder.encode(`event: token\ndata: ${JSON.stringify({ delta })}\n\n`),
          );
        }
        const done = { session_id: sessionId, actions, finish_reason: "stop" };
        controller.enqueue(encoder.encode(`event: done\ndata: ${JSON.stringify(done)}\n\n`));
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      // Espejo de los headers del StreamingResponse real (apps/backend):
      // `Cache-Control: no-cache` evita que un proxy cachee el SSE y
      // `X-Accel-Buffering: no` desactiva el buffering de nginx, para que los
      // tokens lleguen en vivo y el mock sea byte-fiel a producción.
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  }),

  // Perfil (PATCH /v1/users/me) — Fase G. Handlers viven con la feature.
  ...profileHandlers,

  // Memoria — Fase C. Handlers + fixtures viven con la feature.
  ...memoryHandlers,

  // Hoy (tasks/suggestions/recap) — Fase E. PROVISIONAL: sin backend todavía.
  ...todayHandlers,

  // Agenda (eventos día/semana) — Fase F. PROVISIONAL: sin backend todavía.
  ...agendaHandlers,
];
