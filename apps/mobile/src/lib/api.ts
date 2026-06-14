import { configureApi } from "@ynara/core/api";
import { useUserStore } from "@/stores/user";
import { env } from "./env";

// Wiring de plataforma (ADR-012): el cliente HTTP vive en @ynara/core; mobile
// le inyecta su base URL (EXPO_PUBLIC_API_URL) y su token (del user store, que
// persiste en SecureStore). El side-effect corre al importar este módulo.
configureApi({
  baseUrl: env.EXPO_PUBLIC_API_URL,
  getToken: () => useUserStore.getState().token,
});

export { ApiError, api } from "@ynara/core/api";
