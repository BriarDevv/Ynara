import type { CSSProperties } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { cn } from "@/lib/cn";

type Props = {
  /** El guard `guard_against_prod_db_in_dev` está montado y activo. */
  guardActive: boolean;
  /** DSN/host de la DB apuntada (sin credenciales), p.ej. `ynara_dev@localhost:5432`. */
  dbTarget: string;
  /** Verdadero si en entorno dev se está apuntando a una DB de producción. */
  isProdInDev: boolean;
  className?: string;
};

/**
 * Banner prominente de `col-span-12` — lo PRIMERO que ve el operador al entrar a
 * System Health (blueprint §2.3 / §3 F1.6).
 *
 * Tres lecturas posibles:
 *  - **Peligro** (`isProdInDev`): franja `--color-error`, copy en `text-subtitle`.
 *    Es el caso que el guard existe para prevenir: una DB de prod apuntada en dev.
 *  - **Sano** (`guardActive && !isProdInDev`): franja azul plano calmo. El guard
 *    está montado y el target es seguro.
 *  - **Sin guard** (`!guardActive`): tono atenuado (`ink-soft`); el guard no está
 *    activo, no podemos garantizar la separación prod/dev.
 *
 * Sin gradiente, sin hex: borde de acento izquierdo + fondo plano por token.
 */
export function ProdGuardBanner({ guardActive, dbTarget, isProdInDev, className }: Props) {
  // El acento de borde y el dot se mapean al estado. OK = azul plano (decisión de
  // marca: no hay verde en el panel). Peligro = error. Sin guard = ink-soft.
  const accentVar = isProdInDev
    ? "--color-error"
    : guardActive
      ? "--color-blue-flat"
      : "--color-ink-soft";

  const { eyebrow, title } = bannerCopy(guardActive, isProdInDev);

  return (
    <section
      aria-live="polite"
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-6 pl-7 shadow-soft",
        // En peligro la superficie también se tiñe leve de error para que el
        // banner "grite" sin necesidad de un fondo saturado.
        isProdInDev && "bg-[var(--color-error-soft)]",
        className,
      )}
    >
      {/* Borde de acento izquierdo 3px (mismo idioma que el nav activo). */}
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px] rounded-l-[var(--radius-lg)]"
        style={{ backgroundColor: `var(${accentVar})` } as CSSProperties}
      />

      <div className="flex items-start gap-4">
        <Diamond
          size={14}
          color={`var(${accentVar})`}
          variant={isProdInDev ? "solid" : "outline"}
          className={cn("mt-1", !isProdInDev && guardActive && "anim-pulse-soft")}
        />

        <div className="flex flex-col gap-1.5">
          <p className="text-caption text-[var(--color-ink-soft)]">{eyebrow}</p>

          <h2
            className={cn(
              "text-subtitle",
              isProdInDev ? "text-[var(--color-error)]" : "text-[var(--color-ink-deep)]",
            )}
          >
            {title}
          </h2>

          <p className="text-body-sm text-[var(--color-ink-soft)]">
            DB apuntada:{" "}
            <span className="tabular-nums font-medium text-[var(--color-ink)]">{dbTarget}</span>
          </p>
        </div>
      </div>
    </section>
  );
}

/** Copy del banner según el estado del guard. Aislado para legibilidad. */
function bannerCopy(
  guardActive: boolean,
  isProdInDev: boolean,
): { eyebrow: string; title: string } {
  if (isProdInDev) {
    return {
      eyebrow: "Peligro — separación prod/dev rota",
      title: "Estás apuntando a una base de datos de producción en entorno de desarrollo.",
    };
  }
  if (guardActive) {
    return {
      eyebrow: "Guard activo",
      title: "Perímetro de datos protegido — el guard anti-prod está montado.",
    };
  }
  return {
    eyebrow: "Guard inactivo",
    title: "El guard anti-prod no está activo: no se garantiza la separación prod/dev.",
  };
}
