import type { StateStorage } from "zustand/middleware";

/**
 * Storage SSR-safe para los stores persistidos de @ynara/core: en el server
 * de Next no existe `localStorage`, así que las operaciones son no-op y la
 * persistencia recién corre en el cliente tras hidratar.
 */
export const clientStorage: StateStorage = {
  getItem: (name) => (typeof window === "undefined" ? null : window.localStorage.getItem(name)),
  setItem: (name, value) => {
    if (typeof window !== "undefined") window.localStorage.setItem(name, value);
  },
  removeItem: (name) => {
    if (typeof window !== "undefined") window.localStorage.removeItem(name);
  },
};
