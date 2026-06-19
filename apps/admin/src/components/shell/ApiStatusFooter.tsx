"use client";

import { cn } from "@/lib/cn";

/**
 * Footer del rail del Sidebar (blueprint §2.1): dot de estado de la API +
 * latencia en `tabular-nums` + versión de build. El mapeo de color sigue la
 * decisión de marca: OK = azul plano (NO verde — el sistema eliminó el jade a
 * propósito), down = `--color-error`. Mientras no haya endpoint `/system`
 * cableado, muestra un estado neutro (`unknown`) sin inventar datos.
 *
 * Props opcionales: cuando el shell tenga el dato real de `useSystem()` se lo
 * pasa; por ahora el default deja el footer presente y honesto.
 */
type ApiState = "up" | "down" | "unknown";

type Props = {
  state?: ApiState;
  /** Latencia de la API en ms. Si es null, no se muestra número. */
  latencyMs?: number | null;
  /** Versión del build (de `/system` runtime.buildVersion). */
  buildVersion?: string;
  /** Versión colapsada del rail (`<lg`): solo el dot. */
  collapsed?: boolean;
};

const DOT_COLOR: Record<ApiState, string> = {
  up: "var(--color-blue-flat)",
  down: "var(--color-error)",
  unknown: "var(--color-ink-faint)",
};

const STATE_LABEL: Record<ApiState, string> = {
  up: "API operativa",
  down: "API caída",
  unknown: "API · sin chequear",
};

export function ApiStatusFooter({
  state = "unknown",
  latencyMs = null,
  buildVersion,
  collapsed = false,
}: Props) {
  const dot = (
    <span
      aria-hidden
      className={cn("h-2 w-2 shrink-0 rounded-full", state === "up" && "anim-pulse-soft")}
      style={{ backgroundColor: DOT_COLOR[state] }}
    />
  );

  if (collapsed) {
    return (
      <div
        role="img"
        className="flex items-center justify-center py-1"
        title={STATE_LABEL[state]}
        aria-label={STATE_LABEL[state]}
      >
        {dot}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-1.5 py-1 text-caption text-[var(--color-ink-muted)]">
      {dot}
      <span className="text-[var(--color-ink-soft)]">API</span>
      {latencyMs !== null ? (
        <span className="tabular-nums text-[var(--color-ink-soft)]">{latencyMs.toFixed(1)}ms</span>
      ) : null}
      {buildVersion ? <span className="ml-auto truncate tabular-nums">{buildVersion}</span> : null}
    </div>
  );
}
