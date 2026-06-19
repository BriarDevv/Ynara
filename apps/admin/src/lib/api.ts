import { configureApi } from "@ynara/core/api";
import { useAdminStore } from "@/stores/admin";
import { env } from "./env";

// Wiring de plataforma (ADR-012): el cliente HTTP vive en @ynara/core; el panel
// admin le inyecta su base URL (env público) y su token provider (del admin
// store). El side-effect corre al importar este módulo, antes de cualquier
// request (todo call-site importa `api`/`applyAuthHeader` desde acá). El Bearer
// SOLO viaja a nuestra API (perímetro reglas #2/#4, gate en el client de core).
configureApi({
  baseUrl: env.NEXT_PUBLIC_API_URL,
  getToken: () => useAdminStore.getState().token,
});

export { ApiError, api, applyAuthHeader } from "@ynara/core/api";
