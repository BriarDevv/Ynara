import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { clientStorage } from "@/lib/clientStorage";

/**
 * Sesión del operador del panel admin. Patrón espejado del user store del web
 * (token JWT en Zustand persist), pero deliberadamente separado: el panel es
 * interno y su token gatea `require_admin` en el backend, no se mezcla con la
 * sesión del producto. Persiste en localStorage con la key `ynara.admin`.
 *
 * El token lo consume `lib/api.ts` (configureApi.getToken) para adjuntar
 * `Authorization: Bearer <token>` SOLO a nuestra API (perímetro, reglas #2/#4).
 */
export type AdminProfile = {
  adminId: string | null;
  /** Token de sesión admin. Lo lee el cliente API vía getToken. */
  token: string | null;
  displayName: string;
};

type AdminActions = {
  setAuth: (input: { adminId: string; token: string; displayName?: string }) => void;
  setToken: (token: string | null) => void;
  reset: () => void;
};

const initialState: AdminProfile = {
  adminId: null,
  token: null,
  displayName: "",
};

export const useAdminStore = create<AdminProfile & AdminActions>()(
  persist(
    (set) => ({
      ...initialState,
      setAuth: ({ adminId, token, displayName }) =>
        set({ adminId, token, displayName: displayName ?? "" }),
      setToken: (token) => set({ token }),
      reset: () => set(initialState),
    }),
    { name: "ynara.admin", storage: createJSONStorage(() => clientStorage) },
  ),
);
