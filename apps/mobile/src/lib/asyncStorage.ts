import AsyncStorage from "@react-native-async-storage/async-storage";
import type { StateStorage } from "zustand/middleware";

/**
 * Adapter de `StateStorage` (Zustand persist) sobre AsyncStorage. Para el
 * historial del chat (sesiones + mensajes): NO es secreto — el token/perfil van
 * en SecureStore (regla #5) — y persiste entre recargas/reinicios, a diferencia
 * del draft del onboarding (memoryStorage, efímero). AsyncStorage es async;
 * `persist` rehidrata al cargar el store.
 */
export const asyncStorage: StateStorage = {
  getItem: (name) => AsyncStorage.getItem(name),
  setItem: (name, value) => AsyncStorage.setItem(name, value),
  removeItem: (name) => AsyncStorage.removeItem(name),
};
