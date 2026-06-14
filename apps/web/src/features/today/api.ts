// Re-export desde @ynara/core (ADR-012): los hooks de data de "Hoy" se
// comparten con mobile. Se mantiene `@/features/today/api` (y los `../api`
// relativos de los componentes) como superficie estable.

export type { Recap, Suggestion, Task, TasksResponse } from "@ynara/core/features/today";
export { useRecap, useSuggestions, useTasks, useToggleTask } from "@ynara/core/features/today";
