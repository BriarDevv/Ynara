// Re-export desde @ynara/core (ADR-012): la presentación del detalle de memoria
// (resuelve quote/meta/tags/note por capa) se comparte con mobile. Se mantiene
// `@/features/memory/detail-presenter` como superficie estable.

export type { DetailMeta, DetailPresentation } from "@ynara/core/features/memory";
export { presentDetail } from "@ynara/core/features/memory";
