import * as SecureStore from "expo-secure-store";
import type { StateStorage } from "zustand/middleware";

/**
 * Adapter de `StateStorage` (Zustand persist) sobre expo-secure-store.
 *
 * Es el storage del user store, que contiene el JWT: regla #5 de
 * apps/mobile/AGENTS.md exige SecureStore para credenciales (nunca
 * AsyncStorage). Pensado para datos chicos (perfil + token); el estado
 * voluminoso (chat) usa otro storage.
 */
export const secureStorage: StateStorage = {
  getItem: (name) => SecureStore.getItemAsync(name),
  setItem: (name, value) => SecureStore.setItemAsync(name, value),
  removeItem: (name) => SecureStore.deleteItemAsync(name),
};
