/**
 * Factory de query keys de TanStack Query, compartida web + mobile
 * (ADR-012). Keys jerárquicas y tipadas en un solo lugar: las queries y la
 * invalidación leen de acá, así no se desincronizan strings sueltos regados
 * por la app.
 *
 * Convención: `qk.<dominio>.<vista>(...)` devuelve un array `as const`
 * estable. La invalidación por prefijo funciona sola (TanStack matchea por
 * inicio del array): invalidar `qk.memory.all()` alcanza detalle y búsqueda
 * porque comparten el prefijo `["memory"]`.
 *
 * Los dominios se van sumando a medida que cada fase conecta su backend
 * (Memoria → Fase C; Sesiones ya existen; Tareas/Agenda → mock primero).
 */
export const qk = {
  sessions: {
    all: () => ["sessions"] as const,
    detail: (id: string) => ["sessions", id] as const,
  },
  memory: {
    all: (filters?: { layer?: string }) => ["memory", "list", filters ?? {}] as const,
    detail: (layer: string, ref: string) => ["memory", "detail", layer, ref] as const,
    search: (q: string) => ["memory", "search", q] as const,
  },
  today: {
    tasks: () => ["today", "tasks"] as const,
    suggestions: () => ["today", "suggestions"] as const,
    recap: () => ["today", "recap"] as const,
  },
} as const;
