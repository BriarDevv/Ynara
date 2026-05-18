import { setupWorker } from "msw/browser";
import { handlers } from "./api.mocks";

/**
 * Worker MSW para el browser. Se inicia desde providers.tsx en client
 * cuando shouldEnableMocks=true. Usa el service worker generado por
 * `npx msw init public/` (apps/web/public/mockServiceWorker.js).
 */
export const worker = setupWorker(...handlers);
