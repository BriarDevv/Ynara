import { configureApi } from "@ynara/core/api";
import { useUserStore } from "@/stores/user";
import { env } from "./env";

// Wiring de plataforma (ADR-012): el cliente HTTP vive en @ynara/core; la web
// le inyecta su base URL (env público) y su token provider (del user store).
// El side-effect corre al importar este módulo, antes de cualquier request
// (todo call-site importa `api`/`applyAuthHeader` desde acá).
configureApi({
  baseUrl: env.NEXT_PUBLIC_API_URL,
  getToken: () => useUserStore.getState().token,
});

export { ApiError, api, applyAuthHeader } from "@ynara/core/api";
