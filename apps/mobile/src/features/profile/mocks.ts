import { UserOutSchema, UserUpdateSchema } from "@ynara/shared-schemas";

/**
 * Mock-first del dominio **Perfil** (mobile) — maneja `PATCH /v1/users/me`.
 * Se inyecta en el cliente de core vía `configureApi.fetchImpl` (ver `lib/api.ts`),
 * encadenado entre Memoria/Agenda y Hoy. Espeja el estilo Hermes-safe de
 * `memory/mocks.ts` y `agenda/mocks.ts`.
 *
 * Store **mutable**: `currentUser` refleja la última escritura de PATCH para que
 * la demo sea coherente (editar display_name y volver muestra el cambio). No
 * persiste fuera de la sesión.
 */

// ---------- Helpers Hermes-safe (copiados de memory/mocks.ts) ----------

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function parseBody(body: RequestInit["body"]): Record<string, unknown> | null {
  if (typeof body !== "string") return null;
  try {
    const parsed = JSON.parse(body);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

// ---------- Seed del usuario demo ----------

/** UUID estable del usuario de demo — mismo que el seed de memoria. */
const USER_ID = "0193f000-0000-7000-8000-000000000001";
const CREATED_AT = "2024-09-01T12:00:00+00:00";

/**
 * Perfil mutable del usuario demo. `display_name` y `retention_sensitive_days`
 * se mutan con cada PATCH para que la UI refleje el cambio al momento. El resto
 * es estático (email / id / timestamps no cambian en la demo).
 */
const currentUser = {
  id: USER_ID,
  email: "mateo@ynara.app",
  display_name: "Mateo",
  is_ephemeral: false,
  onboarding_completed: true,
  time_zone: "America/Argentina/Buenos_Aires",
  retention_sensitive_days: 365,
  // Espeja la columna JSONB operativa (modos + a11y) del backend, igual que el
  // mock de web: un demo ya onboardeado tiene modos y a11y elegidos.
  preferences: {
    interested_modes: ["productividad", "estudio"],
    a11y: { text_size: "md", high_contrast: false, motion: "auto" },
  },
  created_at: CREATED_AT,
  updated_at: CREATED_AT,
};

/**
 * Handler del dominio Perfil. Devuelve `Response` si el path es de `/v1/users/me`,
 * o `null` si no (para que el dispatcher caiga al siguiente mock / fetch real).
 * Core siempre pasa la URL como string ya resuelta.
 */
export function profileMockResponse(input: string, init?: RequestInit): Response | null {
  const qIndex = input.indexOf("?");
  const path = qIndex >= 0 ? input.slice(0, qIndex) : input;
  const method = (init?.method ?? "GET").toUpperCase();

  if (!path.endsWith("/v1/users/me")) return null;

  // PATCH /v1/users/me — update parcial del perfil.
  if (method === "PATCH") {
    const raw = parseBody(init?.body);

    // Validar con Zod antes de aplicar (espeja el comportamiento de useUpdateMe).
    const parsed = UserUpdateSchema.safeParse(raw);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      return json(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        422,
      );
    }

    // Aplica `exclude_none`: solo los campos presentes en el body se mutan.
    const update = parsed.data;
    if (update.display_name !== undefined) {
      currentUser.display_name = update.display_name;
    }
    if (update.retention_sensitive_days !== undefined) {
      currentUser.retention_sensitive_days = update.retention_sensitive_days;
    }
    if (update.onboarding_completed !== undefined) {
      currentUser.onboarding_completed = update.onboarding_completed;
    }
    currentUser.updated_at = new Date().toISOString();

    // Devuelve el UserOut actualizado, validado con el schema canónico.
    return json(UserOutSchema.parse(currentUser));
  }

  // GET /v1/users/me — perfil actual (para futuros usos; la UI lo lee del store).
  if (method === "GET") {
    return json(UserOutSchema.parse(currentUser));
  }

  return null;
}
