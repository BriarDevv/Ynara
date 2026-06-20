import { defineConfig } from "vitest/config";

// Mismo runner que el resto del monorepo (core/web/admin/shared-schemas).
// Scope: funciones puras de mobile (matemática de fechas, helpers). Entorno
// `node` — sin DOM ni RN: los componentes RN no se testean acá.
export default defineConfig({
  test: {
    environment: "node",
    globals: false,
    include: ["src/**/*.test.ts"],
  },
});
