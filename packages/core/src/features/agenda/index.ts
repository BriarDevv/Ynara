export * from "./api";
export * from "./interaction";
export * from "./layout";
// `expand` (engine de recurrencia con rrule-temporal + Temporal polyfill) NO se
// re-exporta acá a propósito: el barrel lo consume `apps/web` solo por
// `layoutColumns`, y arrastrar el polyfill (~126 KB) al bundle de cliente sería
// peso muerto. Se importa por subpath: `@ynara/core/features/agenda/expand`.
