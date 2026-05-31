/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Config de Vitest para apps/web (unit + componente con RTL).
 *
 * - El alias `@/` mirrorea el `paths` de tsconfig (`@/*` → `./src/*`).
 * - `@ynara/shared-schemas` y `@ynara/ui` se resuelven a su entry de TS
 *   source en el workspace (no hay build step: `main`/`exports` apuntan a
 *   `./src/index.ts`). Los resolvemos manual para no sumar
 *   `vite-tsconfig-paths`.
 * - environment jsdom + globals para no importar `describe/it/expect`.
 * - setupFiles carga jest-dom, mockea matchMedia y limpia el DOM.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@ynara/shared-schemas": fileURLToPath(
        new URL("../../packages/shared-schemas/src/index.ts", import.meta.url),
      ),
      "@ynara/ui": fileURLToPath(new URL("../../packages/ui/src/index.ts", import.meta.url)),
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    clearMocks: true,
    restoreMocks: true,
  },
});
