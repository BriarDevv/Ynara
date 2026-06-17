"use client";

import { useState } from "react";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { MODE_BY_ID } from "@/components/ui/modes";
import { useActiveMode } from "@/hooks/useActiveMode";
import { cn } from "@/lib/cn";
import { useEvents } from "../api";
import { startOfWeek } from "../format";
import { formatDayLong, formatWeekRange, isSameDay } from "../labels";
import { AgendaSkeleton } from "./AgendaSkeleton";
import { DayView } from "./DayView";
import { EventFab } from "./EventFab";
import { ListView } from "./ListView";
import { WeekView } from "./WeekView";

type ViewMode = "lista" | "dia" | "semana";

const VIEW_OPTIONS = [
  { value: "lista", label: "Lista" },
  { value: "dia", label: "Día" },
  { value: "semana", label: "Semana" },
] as const satisfies readonly { value: ViewMode; label: string }[];

const NAV_BUTTON =
  "inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]";

/**
 * Vista **Agenda** — Lista / Día / Semana con grilla horaria (mockup
 * screen-reminders). Fondo vivo `LivingField variant="paper"` (calmo, casi
 * quieto, sin cursor). FAB redondo "+" para crear eventos. Conecta a
 * `GET /v1/events` (mock) vía `useEvents` y resuelve los 4 estados.
 */
export function AgendaView() {
  const activeMode = useActiveMode();
  const [now] = useState(() => new Date());
  const [view, setView] = useState<ViewMode>("semana");
  const [anchor, setAnchor] = useState<Date>(() => new Date());

  const { data, isPending, isError, refetch, isFetching } = useEvents();

  const stepDays = view === "dia" ? 1 : 7;
  const shift = (direction: -1 | 1) => {
    setAnchor((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + direction * stepDays);
      return next;
    });
  };

  const periodLabel =
    view === "dia"
      ? formatDayLong(anchor)
      : view === "lista"
        ? formatWeekRange(startOfWeek(anchor))
        : formatWeekRange(startOfWeek(anchor));

  const onNow =
    view === "dia" ? isSameDay(anchor, now) : isSameDay(startOfWeek(anchor), startOfWeek(now));

  // Tint del modo activo para el FAB
  const tintVar = MODE_BY_ID[activeMode].tintVar;

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo calmo, sin cursor — especificado en el mockup para Agenda */}
      <LivingField variant="paper" modeId={activeMode} />

      <HeroReveal className="mx-auto flex w-full max-w-[720px] flex-1 flex-col gap-6 px-5 pb-24 pt-10 md:px-8">
        <header data-hero-reveal className="flex flex-col gap-4">
          {/* Título grande + período */}
          <div className="flex items-end justify-between gap-3">
            <div>
              <h1 className="text-title text-[var(--color-ink-deep)]">Agenda</h1>
              <p className="text-body text-[var(--color-ink-soft)] mt-1">{periodLabel}</p>
            </div>
            {/* ChipGroup de vistas */}
            <ChipGroup
              options={VIEW_OPTIONS}
              value={view}
              onChange={(v) => {
                setView(v);
                // Al cambiar a lista, volver a la semana actual
                if (v === "lista") setAnchor(new Date());
              }}
            />
          </div>

          {/* Navegación anterior / hoy / siguiente (oculta en lista) */}
          {view !== "lista" && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => shift(-1)}
                aria-label={view === "dia" ? "Día anterior" : "Semana anterior"}
                className={NAV_BUTTON}
              >
                <span aria-hidden>‹</span>
              </button>
              <button
                type="button"
                onClick={() => setAnchor(new Date())}
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
                aria-label={view === "dia" ? "Día siguiente" : "Semana siguiente"}
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
          ) : view === "lista" ? (
            <ListView events={data} now={now} />
          ) : view === "dia" ? (
            <DayView events={data} day={anchor} now={now} />
          ) : (
            <WeekView events={data} anchor={anchor} now={now} />
          )}
        </div>
      </HeroReveal>

      {/* FAB flotante */}
      <EventFab tintVar={tintVar} />
    </div>
  );
}
