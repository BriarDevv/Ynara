"use client";

import { MODE_BY_ID } from "@/components/ui/modes";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import type { Anticipation } from "../anticipations";

type Props = {
  anticipation: Anticipation;
  /** Callback cuando el usuario acciona o descarta la card (MVP: cierra la card). */
  onDismiss: () => void;
};

/**
 * Tarjeta de **Anticipación** (DESIGN.md §8, build-plan E / Hoy):
 * la materialización de "Ynara se adelanta". Glassmorphism suave —
 * fondo semi-transparente + backdrop-blur + borde teñido por el modo —
 * para que el campo vivo se vea detrás.
 *
 * El estado de visibilidad lo maneja el padre (`AnticipationsSection`);
 * esta card es pura presentación + dispara `onDismiss` en cualquier acción.
 *
 * Sin gradientes: §3.4 lo prohíbe fuera de LivingField/YnaraMark/YnaraOrb.
 * El glass usa `color-mix` con transparente, nunca `linear/radial-gradient`.
 */
export function AnticipationCard({ anticipation, onDismiss }: Props) {
  const mode = MODE_BY_ID[anticipation.mode];
  const tint = mode.tintVar;
  const fill = mode.fillVar;

  // Glass: fondo semi-transparente + borde teñido por el modo.
  // `color-mix` en lugar de rgba para mantener la fuente única en tokens.
  const glassBg = `color-mix(in srgb, var(--color-bg) 70%, transparent)`;
  const glassBorder = `color-mix(in srgb, ${tint} 22%, transparent)`;
  const glassShadow = `0 30px 60px -40px color-mix(in srgb, ${tint} 50%, transparent)`;

  return (
    <article
      aria-label={`Anticipación de Ynara: ${anticipation.text}`}
      style={{
        borderRadius: "var(--radius-lg)",
        padding: "18px 18px 16px",
        backgroundColor: glassBg,
        border: `1px solid ${glassBorder}`,
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        boxShadow: glassShadow,
      }}
    >
      {/* Encabezado: orbe + nombre + badge + hora */}
      <div className="mb-3 flex items-center gap-3">
        <YnaraOrb size={34} modeId={anticipation.mode} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="text-body font-semibold text-[var(--color-ink)]">Ynara</span>
            {/* Badge del kind: fill del modo como color de texto (contraste AA)
                sobre un fondo con color-mix de ese mismo fill al 20%. */}
            <span
              className="text-[10px] font-bold tracking-[0.04em]"
              style={{
                padding: "2px 8px",
                borderRadius: "var(--radius-pill)",
                backgroundColor: `color-mix(in srgb, ${fill} 20%, transparent)`,
                color: fill,
              }}
            >
              {anticipation.kind}
            </span>
          </div>
          <span className="text-body-sm tabular-nums text-[var(--color-ink-soft)]">
            {anticipation.time}
          </span>
        </div>
      </div>

      {/* Texto principal */}
      <p className="text-body leading-relaxed text-[var(--color-ink)]">{anticipation.text}</p>

      {/* Acciones */}
      <div className="mt-4 flex gap-2">
        {anticipation.actions.map((action) =>
          action.primary ? (
            <button
              key={action.label}
              type="button"
              onClick={onDismiss}
              className="flex-[1.5] rounded-[var(--radius-md)] py-3 text-[13.5px] font-semibold transition-opacity duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:opacity-90"
              style={{
                // `fill` (no `tint`): tono AA-safe del modo para texto blanco
                // (en memoria el tint es lavanda claro y fallaría AA).
                backgroundColor: fill,
                color: "#fff",
                border: "none",
              }}
            >
              {action.label}
            </button>
          ) : (
            <button
              key={action.label}
              type="button"
              onClick={onDismiss}
              className="flex-1 rounded-[var(--radius-md)] py-3 text-[13.5px] font-semibold text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:text-[var(--color-ink)]"
              style={{
                backgroundColor: "transparent",
                border: "1px solid var(--color-border-strong)",
              }}
            >
              {action.label}
            </button>
          ),
        )}
      </div>
    </article>
  );
}
