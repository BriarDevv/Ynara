import { configureApi } from "@ynara/core/api";
import { todayMockFetch } from "@/features/today/mocks";
import { useUserStore } from "@/stores/user";
import { env } from "./env";

// Wiring de plataforma (ADR-012): el cliente HTTP vive en @ynara/core; mobile
// le inyecta su base URL (EXPO_PUBLIC_API_URL) y su token (del user store, que
// persiste en SecureStore). El side-effect corre al importar este módulo.
configureApi({
  baseUrl: env.EXPO_PUBLIC_API_URL,
  getToken: () => useUserStore.getState().token,
  // Mock-first del dominio "Hoy" (todavía no hay backend de tareas): con el flag
  // prendido, el mock-fetch sirve /v1/tasks|suggestions|recap canned y delega el
  // resto —auth incluido— al fetch real. Off → fetch global directo (default).
  ...(env.EXPO_PUBLIC_ENABLE_MOCKS ? { fetchImpl: todayMockFetch } : {}),
});

export { ApiError, api } from "@ynara/core/api";
