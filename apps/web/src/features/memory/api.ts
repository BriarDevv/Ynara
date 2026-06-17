// Re-export desde @ynara/core (ADR-012): los hooks de data de memoria se
// comparten con mobile. Se mantiene `@/features/memory/api` (y los `../api`
// relativos de los componentes) como superficie estable.

export type { MemoryPatch, TimelineFilter } from "@ynara/core/features/memory";
export {
  SEARCH_MIN_LENGTH,
  useDeleteMemory,
  useMemoryDetail,
  useMemoryExport,
  useMemoryRelated,
  useMemorySearch,
  useMemoryTimeline,
  useMemoryWipeExecute,
  useMemoryWipePreview,
  usePatchMemory,
} from "@ynara/core/features/memory";

// Tipos del dominio wipe/export (Fase G — tab Tú).
export type {
  MemoryExport,
  MemoryWipeConfirm,
  MemoryWipePreview,
  MemoryWipeResult,
} from "@ynara/shared-schemas";
