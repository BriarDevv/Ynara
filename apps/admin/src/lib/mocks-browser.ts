import { setupWorker } from "msw/browser";

/**
 * Worker MSW para el browser. Se inicia desde `providers.tsx` en client cuando
 * `shouldEnableMocks=true`, y usa el service worker generado por
 * `npx msw init public/` (apps/admin/public/mockServiceWorker.js).
 *
 * Los handlers de los endpoints `/v1/admin/*` se cablean en F1 desde
 * `@/fixtures/handlers` (sirven los fixtures parseados por su Zod). Hasta
 * entonces el worker arranca con un set vacío + `onUnhandledRequest: "bypass"`,
 * así no bloquea el dev server del scaffold.
 */
export const worker = setupWorker();
