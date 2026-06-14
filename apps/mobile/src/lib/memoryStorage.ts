import type { StateStorage } from "zustand/middleware";

/**
 * Storage en memoria para el draft del onboarding (Zustand persist).
 *
 * En la web el draft vive en sessionStorage ("sobrevive al refresh, se pierde
 * al cerrar el tab"). En mobile no hay ese ciclo de refresh y escribir en
 * SecureStore/AsyncStorage en cada tecla del nombre sería innecesario y con
 * jank. El draft es de una sola sesión, así que alcanza con memoria: zustand
 * mantiene el estado igual, esto solo satisface la API de `persist`.
 */
const store = new Map<string, string>();

export const memoryStorage: StateStorage = {
  getItem: (name) => store.get(name) ?? null,
  setItem: (name, value) => {
    store.set(name, value);
  },
  removeItem: (name) => {
    store.delete(name);
  },
};
