"use client";

import { useState } from "react";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID } from "@/components/ui/modes";
import { useActiveMode } from "@/hooks/useActiveMode";
import { cn } from "@/lib/cn";
import { useEvents } from "../api";
import { startOfWeek } from "../format";
import { formatDayLong, formatWeekRange, isSameDay } from "../labels";
import { AgendaSkeleton } from "./AgendaSkeleton";
import { DayView } from "./DayView";
import { WeekView } from "./WeekView";

type ViewMode = "dia" | "semana";

const VIEW_OPTIONS = [
  { value: "dia", label: "Día" },
  { value: "semana", label: "Semana" },
] as const satisfies readonly { value: ViewMode; label: string }[];

const NAV_BUTTON =
  "inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-ink)] hover:text-[var(--color-ink)]";

/**
 * Vista **Agenda** — el día/semana de bloques horarios (wireframes 10/11,
 * build-plan Fase F). Toggle día↔semana (`ChipGroup`), navegación
 * anterior/hoy/siguiente, y el fondo vivo (`LivingField` aurora) teñido por el
 * modo activo del usuario, en paridad con Hoy.
 *
 * Default **semana**: muestra todos los bloques de la semana de una, en vez de
 * arrancar en un día que puede estar vacío. Conecta a `GET /v1/events` (mock)
 * vía `useEvents` y resuelve los 4 estados (cargando/error/vacío/datos); el
 * filtrado por día lo hacen las sub-vistas sobre la lista.
 *
 * `now` se fija una vez por montaje para anclar "hoy" sin drift; `anchor` es el
 * día/semana en foco, que la navegación desplaza.
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

  const periodLabel = view === "dia" ? formatDayLong(anchor) : formatWeekRange(startOfWeek(anchor));
  const onNow =
    view === "dia" ? isSameDay(anchor, now) : isSameDay(startOfWeek(anchor), startOfWeek(now));

  return (
    <div className="relative isolate flex min-h-full flex-col">
      <LivingField variant="aurora" modeId={activeMode} />

      <HeroReveal className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-8 px-6 pb-8 pt-10">
        <header data-hero-reveal className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3">
            <ModeChip
              modeId={activeMode}
              variant="soft"
              label={`Modo: ${MODE_BY_ID[activeMode].label}`}
            />
            <ChipGroup options={VIEW_OPTIONS} value={view} onChange={setView} />
          </div>

          <div className="flex flex-col gap-1">
            <h1 className="text-title text-[var(--color-ink-deep)]">Agenda</h1>
            <p className="text-body text-[var(--color-ink-soft)]">{periodLabel}</p>
          </div>

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
        </header>

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
          ) : view === "dia" ? (
            <DayView events={data} day={anchor} />
          ) : (
            <WeekView events={data} anchor={anchor} now={now} />
          )}
        </div>
      </HeroReveal>
    </div>
  );
}
