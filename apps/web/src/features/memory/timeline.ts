// Re-export desde @ynara/core (ADR-012): los helpers puros del timeline de
// memoria (aplanado de capas, agrupado por bucket, formato de fechas) se
// comparten con mobile. Se mantiene `@/features/memory/timeline` como
// superficie estable para componentes y tests de web.

export type { TimelineEntry, TimelineGroup } from "@ynara/core/features/memory";
export {
  entriesForLayer,
  formatEntryDate,
  formatFullDate,
  groupByBucket,
  humanizeKey,
  relatedEntries,
  sessionRefOf,
  toTimelineEntries,
} from "@ynara/core/features/memory";
