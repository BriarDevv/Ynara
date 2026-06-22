import { configureApi } from "@ynara/core/api";
import { useUserStore } from "@/stores/user";
import { env } from "./env";

// Wiring de plataforma (ADR-012): el cliente HTTP vive en @ynara/core; la web
// le inyecta su base URL (env público) y su token provider (del user store).
// El side-effect corre al importar este módulo, antes de cualquier request
// (todo call-site importa `api`/`applyAuthHeader` desde acá).
configureApi({
  baseUrl: env.NEXT_PUBLIC_API_URL,
  getToken: () => {
    const fromStore = useUserStore.getState().token;
    if (fromStore) return fromStore;
    // Fallback anti-race de hidratación: en un reload DURO, una query autenticada
    // (p.ej. GET /v1/tasks en /hoy) puede dispararse ANTES de que zustand rehidrate
    // el token desde localStorage, devolviendo un 401 espurio que rompe la pantalla.
    // El token SÍ está persistido bajo "ynara.user" (ver createUserStore), así que lo
    // leemos directo como red de seguridad solo cuando el store todavía está en null.
    // El store sigue siendo la fuente de verdad; esto cubre únicamente la ventana de
    // hidratación. SSR-safe (no toca window en el server) y a prueba de JSON corrupto.
    if (typeof window === "undefined") return null;
    try {
      const raw = window.localStorage.getItem("ynara.user");
      if (!raw) return null;
      const token = (JSON.parse(raw) as { state?: { token?: string | null } })?.state?.token;
      return token ?? null;
    } catch {
      return null;
    }
  },
});

export { ApiError, api, applyAuthHeader } from "@ynara/core/api";
