import type { RangeId } from "@/stores/range";

/**
 * Factory de query keys del panel admin. Mismo patrón jerárquico que
 * `@ynara/core/query-keys` (`qk.<dominio>.<vista>(...)` → array `as const`),
 * pero local a esta app: el dominio `admin` no existe en core (es interno del
 * panel) y no queremos acoplar core a vistas de soberanía.
 *
 * Convención: la mayoría de las vistas se segmentan por `range` (la ventana
 * temporal global). `system` no lleva range (es runtime/config, no negocio).
 * La invalidación por prefijo funciona sola: invalidar `["admin"]` alcanza
 * todas las vistas; `["admin","audit"]` alcanza todas sus páginas.
 *
 * `audit` además clava `filters`/`page` en la key para que cada combinación de
 * filtros + paginación tenga su entrada de cache independiente.
 */
export const qk = {
  admin: {
    all: () => ["admin"] as const,
    overview: (range: RangeId) => ["admin", "overview", range] as const,
    users: (range: RangeId) => ["admin", "users", range] as const,
    modes: (range: RangeId) => ["admin", "modes", range] as const,
    moat: (range: RangeId) => ["admin", "moat", range] as const,
    audit: (range: RangeId, filters: unknown, page: number) =>
      ["admin", "audit", range, filters, page] as const,
    system: () => ["admin", "system"] as const,
    playground: () => ["admin", "playground"] as const,
  },
} as const;
