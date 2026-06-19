import { setupWorker } from "msw/browser";
import { adminHandlers } from "@/fixtures/handlers";

/**
 * Worker MSW para el browser. Se inicia desde `providers.tsx` en client cuando
 * `shouldEnableMocks=true`, y usa el service worker generado por
 * `npx msw init public/` (apps/admin/public/mockServiceWorker.js).
 *
 * Cablea los handlers de `/v1/admin/*` desde `@/fixtures/handlers` (cada uno
 * sirve el fixture ya parseado por su Zod). El arranque usa
 * `onUnhandledRequest: "bypass"` (en `providers.tsx`) para no romper requests
 * fuera del set de admin (assets de Next, etc.).
 */
export const worker = setupWorker(...adminHandlers);
