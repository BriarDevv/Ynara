"use client";

import { useMemo, useState } from "react";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { useActiveMode } from "@/hooks/useActiveMode";
import { buildAnticipations } from "../anticipations";
import { AnticipationCard } from "./AnticipationCard";

/**
 * Vista **Avisos** — pantalla de anticipaciones proactivas de Ynara
 * (mockup screen-reminders.jsx / AvisosScreen).
 *
 * Activos: cards glass reutilizando `AnticipationCard` + `onDismiss`
 * que mueve el ítem a la lista de resueltos (estado local, mock sin backend).
 * Resueltos: filas calmas con check y texto "Listo. Lo dejé resuelto por vos."
 * Pie: nota sobre Premium.
 *
 * Sin gradientes de UI (guard §3.4): superficies glass con `--color-glass`
 * y fill AA-safe para texto blanco sobre color de modo.
 */
export function AvisosView() {
  const activeMode = useActiveMode();
  const initial = useMemo(() => buildAnticipations(), []);
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());

  const active = initial.filter((a) => !resolvedIds.has(a.id));
  const resolved = initial.filter((a) => resolvedIds.has(a.id));

  function resolve(id: string) {
    setResolvedIds((prev) => new Set([...prev, id]));
  }

  const pendientes = active.length;
  const subline =
    pendientes > 0
      ? `Ynara se adelanta. ${pendientes} ${pendientes === 1 ? "cosa" : "cosas"} para hoy.`
      : "Todo al día.";

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo vivo (variante depth: profundidad + atmósfera). */}
      <LivingField variant="depth" modeId={activeMode} />

      <HeroReveal className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-8 px-6 pb-8 pt-10">
        {/* Header */}
        <div data-hero-reveal>
          <h1 className="text-title font-semibold leading-tight tracking-tight text-[var(--color-ink)]">
            Avisos
          </h1>
          <p className="mt-1.5 text-body-sm text-[var(--color-ink-soft)]">{subline}</p>
        </div>

        {/* Activos */}
        {active.length > 0 && (
          <section
            aria-label="Avisos activos"
            aria-live="polite"
            className="flex flex-col gap-3"
            data-hero-reveal
          >
            {active.map((anticipation) => (
              <AnticipationCard
                key={anticipation.id}
                anticipation={anticipation}
                onDismiss={() => resolve(anticipation.id)}
              />
            ))}
          </section>
        )}

        {/* Resueltos */}
        {resolved.length > 0 && (
          <section aria-label="Avisos resueltos" data-hero-reveal>
            <p className="mb-2 px-0.5 text-caption font-bold uppercase tracking-[0.14em] text-[var(--color-ink-faint)]">
              Resueltos
            </p>
            <ul className="flex flex-col" aria-live="polite">
              {resolved.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center gap-3 border-b border-[var(--color-border)] py-3 last:border-b-0"
                  style={{ opacity: 0.7 }}
                >
                  {/* Check calmo (decorativo) */}
                  <svg
                    role="img"
                    aria-label="Resuelto"
                    width="18"
                    height="18"
                    viewBox="0 0 18 18"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="shrink-0"
                  >
                    <title>Resuelto</title>
                    <path
                      d="M3.5 9.5 7 13 14.5 5.5"
                      stroke="var(--color-ink-soft)"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span className="text-body-sm text-[var(--color-ink-soft)]">
                    Listo. Lo dejé resuelto por vos.
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Nota Premium */}
        <footer
          className="flex items-center justify-center gap-2 pt-2 text-caption text-[var(--color-ink-faint)]"
          data-hero-reveal
        >
          {/* Punto decorativo en lugar de ícono inexistente */}
          <span
            aria-hidden
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: "var(--color-ink-faint)" }}
          />
          Los avisos proactivos son parte de Premium
        </footer>
      </HeroReveal>
    </div>
  );
}
