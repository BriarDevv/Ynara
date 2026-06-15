import { randomUUID } from "expo-crypto";

/**
 * Polyfill de `crypto.randomUUID` para React Native / Hermes (no lo trae nativo,
 * landmine documentado en FRONTEND-CHAT-PLAN.md §9). Lo necesita el chat store
 * de @ynara/core, que genera ids de sesión/mensaje con `crypto.randomUUID()`.
 *
 * Se importa primero en `_layout.tsx` (boot), antes de que cualquier pantalla
 * toque el store. Solo agrega `randomUUID` si falta (no pisa un crypto nativo).
 */
const g = globalThis as unknown as { crypto?: { randomUUID?: () => string } };

if (!g.crypto) {
  g.crypto = { randomUUID };
} else if (typeof g.crypto.randomUUID !== "function") {
  g.crypto.randomUUID = randomUUID;
}
