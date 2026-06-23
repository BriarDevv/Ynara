"use client";

import { useState } from "react";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { MODE_BY_ID } from "@/components/ui/modes";
import { useActiveMode } from "@/hooks/useActiveMode";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/cn";
import { type AgendaEvent, useEvents } from "../api";
import { startOfWeek } from "../format";
import { formatDayLong, formatMonthYear, formatWeekRange, isSameDay, isSameMonth } from "../labels";
import { AgendaSkeleton } from "./AgendaSkeleton";
import { DayView } from "./DayView";
import { EventEditSheet } from "./EventEditSheet";
import { EventFab } from "./EventFab";
import { ListView } from "./ListView";
import { MonthView } from "./MonthView";
import { WeekView } from "./WeekView";

type ViewMode = "lista" | "dia" | "semana" | "mes";

const VIEW_OPTIONS = [
  { value: "lista", label: "Lista" },
  { value: "dia", label: "Día" },
  { value: "semana", label: "Semana" },
  { value: "mes", label: "Mes" },
] as const satisfies readonly { value: ViewMode; label: string }[];

// La grilla de 7 columnas es el patrón equivocado en un teléfono (celdas
// ilegibles bajo ~360px: ninguna app líder la muestra en vertical). En mobile
// la Agenda vive en Lista/Día; "Semana" queda como vista desktop-only.
const DESKTOP_QUERY = "(min-width: 768px)";

const NAV_BUTTON =
  "inline-flex h-11 w-11 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]";

/**
 * Vista **Agenda** — Lista / Día / Semana con grilla horaria (mockup
 * screen-reminders). Fondo vivo `LivingField variant="paper"` (calmo, casi
 * quieto, sin cursor). FAB redondo "+" para crear eventos. Conecta a
 * `GET /v1/events` (mock) vía `useEvents` y resuelve los 4 estados.
 */
export function AgendaView() {
  const activeMode = useActiveMode();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const [now] = useState(() => new Date());
  const [view, setView] = useState<ViewMode>("lista");
  const [anchor, setAnchor] = useState<Date>(() => new Date());
  // Evento en edición (tap-para-editar); `null` = sheet cerrado.
  const [editing, setEditing] = useState<AgendaEvent | null>(null);

  const { data, isPending, isError, refetch, isFetching } = useEvents();

  // "Semana" solo existe en desktop. En mobile se oculta del switcher y, si
  // quedó seteada al venir de un viewport ancho, cae a Lista para no renderizar
  // la grilla de 7 columnas en pantalla angosta.
  const viewOptions = isDesktop
    ? VIEW_OPTIONS
    : VIEW_OPTIONS.filter((opt) => opt.value !== "semana");
  const effectiveView: ViewMode = !isDesktop && view === "semana" ? "lista" : view;

  const shift = (direction: -1 | 1) => {
    setAnchor((prev) => {
      const next = new Date(prev);
      if (effectiveView === "mes") {
        next.setMonth(next.getMonth() + direction);
      } else {
        next.setDate(next.getDate() + direction * (effectiveView === "dia" ? 1 : 7));
      }
      return next;
    });
  };

  // Ancla la vista a "ahora". Vive en un handler (corre solo en el browser al
  // interactuar), por eso `new Date()` acá no puede causar hydration mismatch.
  const goToNow = () => setAnchor(new Date());

  // Etiqueta de la unidad navegable (para los aria-label de prev/next).
  const unitLabel = effectiveView === "dia" ? "Día" : effectiveView === "mes" ? "Mes" : "Semana";

  const periodLabel =
    effectiveView === "dia"
      ? formatDayLong(anchor)
      : effectiveView === "mes"
        ? formatMonthYear(anchor)
        : formatWeekRange(startOfWeek(anchor));

  const onNow =
    effectiveView === "dia"
      ? isSameDay(anchor, now)
      : effectiveView === "mes"
        ? isSameMonth(anchor, now)
        : isSameDay(startOfWeek(anchor), startOfWeek(now));

  // Fill (AA-safe) del modo activo para el FAB con el "+" blanco.
  const fabFill = MODE_BY_ID[activeMode].fillVar;

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo calmo, sin cursor — especificado en el mockup para Agenda */}
      <LivingField variant="paper" modeId={activeMode} />

      <HeroReveal className="mx-auto flex w-full max-w-[720px] flex-1 flex-col gap-6 px-6 pb-24 pt-10 md:px-8">
        <header data-hero-reveal className="flex flex-col gap-4">
          {/* Título grande + período */}
          <div className="flex items-end justify-between gap-3">
            <div>
              <h1 className="text-title text-[var(--color-ink-deep)]">Agenda</h1>
              <p className="text-body text-[var(--color-ink-soft)] mt-1">{periodLabel}</p>
            </div>
            {/* ChipGroup de vistas */}
            <ChipGroup
              ariaLabel="Vista de agenda"
              options={viewOptions}
              value={effectiveView}
              onChange={(v) => {
                setView(v);
                // Al cambiar a lista, volver a la semana actual
                if (v === "lista") goToNow();
              }}
            />
          </div>

          {/* Navegación anterior / hoy / siguiente (oculta en lista) */}
          {effectiveView !== "lista" && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => shift(-1)}
                aria-label={`${unitLabel} anterior`}
                className={NAV_BUTTON}
              >
                <span aria-hidden>‹</span>
              </button>
              <button
                type="button"
                onClick={goToNow}
                disabled={onNow}
                className={cn(
                  "text-button rounded-[var(--radius-pill)] px-4 py-2 text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:text-[var(--color-ink)]",
                  "disabled:opacity-40 disabled:hover:text-[var(--color-ink-soft)]",
                )}
              >
                Hoy
              </button>
              <button
                type="button"
                onClick={() => shift(1)}
                aria-label={`${unitLabel} siguiente`}
                className={NAV_BUTTON}
              >
                <span aria-hidden>›</span>
              </button>
            </div>
          )}
        </header>

        {/* Contenido principal: 4 estados */}
        <div data-hero-reveal>
          {isPending ? (
            <AgendaSkeleton />
          ) : isError ? (
            <EmptyStateCard
              title="No pudimos traer tu agenda"
              hint="Puede ser un problema de conexión. Probá de nuevo."
              action={
                <button
                  type="button"
                  onClick={() => refetch()}
                  disabled={isFetching}
                  className="text-button text-[var(--color-ink)] underline underline-offset-4 disabled:opacity-50"
                >
                  Reintentar
                </button>
              }
            />
          ) : effectiveView === "lista" ? (
            <ListView events={data} now={now} onEventClick={setEditing} />
          ) : effectiveView === "dia" ? (
            <DayView events={data} day={anchor} now={now} onEventClick={setEditing} />
          ) : effectiveView === "mes" ? (
            <MonthView
              events={data}
              anchor={anchor}
              now={now}
              onSelectDay={(day) => {
                setAnchor(day);
                setView("dia");
              }}
            />
          ) : (
            <WeekView events={data} anchor={anchor} now={now} onEventClick={setEditing} />
          )}
        </div>
      </HeroReveal>

      {/* FAB flotante */}
      <EventFab fillVar={fabFill} activeMode={activeMode} />

      {/* Sheet de edición (tap-para-editar): se abre al tocar un evento. */}
      <EventEditSheet event={editing} onClose={() => setEditing(null)} />
    </div>
  );
}
