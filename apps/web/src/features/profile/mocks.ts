import type { ApiErrorBody, UserOut } from "@ynara/shared-schemas";
import { UserUpdateSchema } from "@ynara/shared-schemas";
import { HttpResponse, http } from "msw";
import { env } from "@/lib/env";

/**
 * Handlers MSW del perfil (`PATCH /v1/users/me`).
 *
 * Mantiene un `currentUser` mutable seedeado con datos de demo; valida el body
 * con `UserUpdateSchema` (mirror del Pydantic del backend) y aplica solo los
 * campos enviados (`exclude_none`). Espeja el contrato real — al apuntar al
 * backend real (apagar mocks) la UI no cambia.
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

// Usuario de demo seedeado. UUID estable para que los links de prueba no roten.
// `preferences` espeja la columna JSONB operativa (modos + a11y) que el backend
// devuelve desde G2: un usuario demo ya onboardeado tiene modos y a11y elegidos.
let currentUser: UserOut = {
  id: "0193f010-0000-7000-8000-000000000001",
  email: "mateo@ynara.app",
  display_name: "Mateo",
  onboarding_completed: true,
  retention_sensitive_days: 365,
  preferences: {
    interested_modes: ["productividad", "estudio"],
    a11y: { text_size: "md", high_contrast: false, motion: "auto" },
  },
  created_at: "2025-01-01T00:00:00+00:00",
  updated_at: new Date().toISOString(),
};

function errorResponse(body: ApiErrorBody, status: number) {
  return HttpResponse.json(body, { status });
}

export const profileHandlers = [
  // `PATCH /v1/users/me` — update parcial del perfil propio. Valida con Zod y
  // aplica solo los campos presentes (exclude_none: un PATCH sin campos es no-op).
  http.patch(apiUrl("/v1/users/me"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = UserUpdateSchema.safeParse(json);

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

    // Aplica solo los campos presentes (exclude_none).
    const update = parsed.data;
    if (update.display_name !== undefined) {
      currentUser = { ...currentUser, display_name: update.display_name };
    }
    if (update.onboarding_completed !== undefined) {
      currentUser = { ...currentUser, onboarding_completed: update.onboarding_completed };
    }
    if (update.retention_sensitive_days !== undefined) {
      currentUser = { ...currentUser, retention_sensitive_days: update.retention_sensitive_days };
    }
    currentUser = { ...currentUser, updated_at: new Date().toISOString() };

    return HttpResponse.json(currentUser);
  }),
];
