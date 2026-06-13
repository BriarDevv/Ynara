// Re-export desde @ynara/core (ADR-012): la factory de query keys se
// comparte con mobile. Se mantiene este módulo como punto de import estable
// para la web (`@/lib/queryKeys`), evitando tocar los call-sites existentes.
export { qk } from "@ynara/core/query-keys";
