// Re-export desde @ynara/core (ADR-012): los hooks de data del perfil se
// comparten con mobile. Se mantiene `@/features/profile/api` como superficie
// estable para los componentes de esta feature.

export type { UserOut, UserUpdate } from "@ynara/core/features/profile";
export { useMe, useUpdateMe } from "@ynara/core/features/profile";
