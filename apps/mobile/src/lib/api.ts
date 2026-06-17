import { configureApi } from "@ynara/core/api";
import { agendaMockResponse } from "@/features/agenda/mocks";
import { memoryMockResponse } from "@/features/memory/mocks";
import { todayMockFetch } from "@/features/today/mocks";
import { useUserStore } from "@/stores/user";
import { env } from "./env";

// Mock-first encadenado por dominio: Memoria y Agenda responden sync
// (Response | null); si el path no es de ninguno, cae al mock de Hoy, que
// maneja sus paths o delega el resto —auth incluido— al fetch real. Con el
// flag off no se setea fetchImpl (queda el default = fetch global).
const mockFetch: (input: string, init?: RequestInit) => Promise<Response> = (input, init) => {
  const mem = memoryMockResponse(input, init);
  if (mem) return Promise.resolve(mem);
  const agenda = agendaMockResponse(input, init);
  if (agenda) return Promise.resolve(agenda);
  return todayMockFetch(input, init);
};

// Wiring de plataforma (ADR-012): el cliente HTTP vive en @ynara/core; mobile
// le inyecta su base URL (EXPO_PUBLIC_API_URL) y su token (del user store, que
// persiste en SecureStore). El side-effect corre al importar este módulo.
configureApi({
  baseUrl: env.EXPO_PUBLIC_API_URL,
  getToken: () => useUserStore.getState().token,
  ...(env.EXPO_PUBLIC_ENABLE_MOCKS ? { fetchImpl: mockFetch } : {}),
});

export { ApiError, api } from "@ynara/core/api";
