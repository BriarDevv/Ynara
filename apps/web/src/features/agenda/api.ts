// Re-export desde @ynara/core (ADR-012): los hooks de Agenda se comparten con
// mobile. Se mantiene `@/features/agenda/api` (y los `../api` relativos de los
// componentes) como superficie estable.

export type {
  AgendaEvent,
  EventCreate,
  EventPatch,
  EventsResponse,
} from "@ynara/core/features/agenda";
export {
  useCreateEvent,
  useDeleteEvent,
  useEvents,
  usePatchEvent,
} from "@ynara/core/features/agenda";
