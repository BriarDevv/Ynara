"use client";

import { Icon } from "@ynara/ui";
import { useEffect, useState } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { LivingField } from "@/components/ui/LivingField";
import { PromptChip } from "@/components/ui/PromptChip";
import { useActiveMode } from "@/hooks/useActiveMode";
import { SEARCH_MIN_LENGTH, useMemorySearch } from "../api";
import { MemoryTimelineSkeleton } from "./MemoryTimelineSkeleton";
import { SearchResultRow } from "./SearchResultRow";

/** Disparadores de búsqueda (matchean el dataset de demo). */
const SUGGESTIONS = ["tesis", "brief de Õmi", "jerga técnica", "foco"] as const;

const DEBOUNCE_MS = 250;

// Ícono `leading` estable para los chips de sugerencia: idéntico en cada chip,
// así que vive a nivel de módulo y no se reconstruye por render.
const SUGGESTION_ICON = <Icon name="buscar" size={16} />;

/**
 * Vista **Búsqueda** (wireframes 18/19 / build-plan C3). Input con debounce que
 * pega a `GET /v1/memory/search` (PROVISIONAL, mock por ahora) y resuelve los
 * estados: vacío (sugerencias), cargando (skeleton), resultados ("N RESULTADOS"
 * + lista) y sin resultados. Sube fidelidad sobre el wireframe de media con el
 * design system v2.
 */
export function BuscarView({ initialQuery = "" }: { initialQuery?: string }) {
  const [input, setInput] = useState(initialQuery);
  const [debounced, setDebounced] = useState(initialQuery);
  const [now] = useState(() => new Date());
  const activeMode = useActiveMode();

  // Debounce: la query efectiva sigue al input con un respiro, así no se dispara
  // un fetch por cada tecla.
  useEffect(() => {
    const id = setTimeout(() => setDebounced(input), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [input]);

  // Sincronizar la query con la URL (?q=) para que el link sea compartible (la
  // página lo promete y la ruta ya lee ?q= como initialQuery). `replaceState`
  // actualiza la barra sin re-navegar ni re-correr el server component por tecla.
  useEffect(() => {
    const q = debounced.trim();
    const url = q ? `/buscar?q=${encodeURIComponent(q)}` : "/buscar";
    window.history.replaceState(null, "", url);
  }, [debounced]);

  const active = debounced.trim().length >= SEARCH_MIN_LENGTH;
  const search = useMemorySearch(debounced);

  // Mensaje conciso para la región viva sr-only (M1): el contenido visual de
  // resultados cambia sin avisar al lector de pantalla, así que anunciamos el
  // estado/recuento al settle de cada búsqueda (debounced, no por tecla).
  const liveStatus = !active
    ? ""
    : search.isLoading
      ? "Buscando…"
      : search.isError
        ? "No pudimos completar la búsqueda."
        : search.data && search.data.total === 0
          ? `Sin resultados para «${search.data.query}».`
          : search.data
            ? `${search.data.total} ${search.data.total === 1 ? "resultado" : "resultados"} para «${search.data.query}».`
            : "";

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo vivo de Búsqueda (network: misma textura que Memoria, de la que
          es una vista hermana — DESIGN.md §2.2), teñido por el modo activo. */}
      <LivingField variant="network" modeId={activeMode} />

      <div className="mx-auto flex w-full max-w-[680px] flex-col gap-6 px-6 pb-10 pt-10">
        <h1 className="text-title text-[var(--color-ink-deep)]">Buscar</h1>

        {/* Buscador como única superficie suave de la vista: vidrio sobre el
            campo vivo (`--color-glass` se vuelve sólido con
            prefers-reduced-transparency) + blur, con el borde teñido por la
            memoria al enfocar. */}
        <div className="flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-glass)] px-4 backdrop-blur-md transition-colors duration-[var(--duration-fast)] focus-within:border-[var(--color-memory)]">
          <Icon name="buscar" size={20} className="shrink-0 text-[var(--color-ink-soft)]" />
          <input
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Buscá en tu memoria…"
            aria-label="Buscar en tu memoria"
            className="text-body min-h-[48px] w-full bg-transparent text-[var(--color-ink)] placeholder:text-[var(--color-ink-soft)] focus:outline-none [&::-webkit-search-cancel-button]:appearance-none"
          />
          {input.length > 0 ? (
            <button
              type="button"
              onClick={() => setInput("")}
              aria-label="Limpiar búsqueda"
              className="shrink-0 text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] hover:text-[var(--color-ink)]"
            >
              <Icon name="cerrar" size={18} />
            </button>
          ) : null}
        </div>

        {/* Región viva: anuncia estado/resultados al lector de pantalla (el
            contenido visual de abajo cambia sin avisar — M1). `<output>` ya
            implica role=status + aria-live=polite + aria-atomic; lo explicitamos. */}
        <output aria-live="polite" className="sr-only">
          {liveStatus}
        </output>

        {!active ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-caption text-[var(--color-ink-soft)]">Probá buscar</h2>
            <ul className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <PromptChip label={s} leading={SUGGESTION_ICON} onClick={() => setInput(s)} />
                </li>
              ))}
            </ul>
          </section>
        ) : search.isLoading ? (
          <MemoryTimelineSkeleton rows={3} />
        ) : search.isError ? (
          <EmptyStateCard
            title="No pudimos buscar"
            hint="Puede ser un problema de conexión. Probá de nuevo en un momento."
          />
        ) : search.data && search.data.total === 0 ? (
          <EmptyStateCard
            title={`Nada para «${search.data.query}»`}
            hint="Probá con otras palabras, o revisá el timeline completo."
          />
        ) : search.data ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-caption text-[var(--color-ink-soft)]">
              {search.data.total} {search.data.total === 1 ? "resultado" : "resultados"}
            </h2>
            <ul
              aria-busy={search.isFetching}
              className="flex flex-col divide-y divide-[var(--color-border)]"
            >
              {search.data.results.map((hit, i) => (
                <SearchResultRow
                  key={`${hit.layer}:${hit.ref}`}
                  hit={hit}
                  now={now}
                  index={i}
                  query={search.data.query}
                />
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}
