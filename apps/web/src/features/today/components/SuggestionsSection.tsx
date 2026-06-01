"use client";

import { useSuggestions } from "../api";
import { SuggestionCard } from "./SuggestionCard";
import { SuggestionsSkeleton } from "./SuggestionsSkeleton";

/**
 * Sección **Ynara sugiere** (wireframe 06/07 / build-plan E3). Conecta a
 * `GET /v1/suggestions` (mock). Las sugerencias son secundarias respecto de las
 * prioridades, así que los estados son más livianos: si no hay ninguna, la
 * sección no se muestra; el error es una línea discreta con reintento.
 */
export function SuggestionsSection() {
  const { data, isPending, isError, refetch, isFetching } = useSuggestions();

  if (isError) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-caption text-[var(--color-ink-soft)]">Ynara sugiere</h2>
        <p className="text-body-sm text-[var(--color-ink-muted)]">
          No pudimos traer las sugerencias.{" "}
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-[var(--color-ink)] underline underline-offset-4 disabled:opacity-50"
          >
            Reintentar
          </button>
        </p>
      </section>
    );
  }

  // Sin sugerencias → no mostramos la sección vacía (no prometemos contenido).
  if (!isPending && data.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-caption text-[var(--color-ink-muted)]">Ynara sugiere</h2>
      {isPending ? (
        <SuggestionsSkeleton />
      ) : (
        <ul className="flex flex-col gap-3">
          {data.map((suggestion, index) => (
            <SuggestionCard key={suggestion.id} suggestion={suggestion} index={index} />
          ))}
        </ul>
      )}
    </section>
  );
}
