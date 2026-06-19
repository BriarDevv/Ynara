"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";
import { fmtMs } from "@/lib/time";

type Service = "postgres" | "redis";

type Props = {
  /** Servicio de infra al que pertenece esta tarjeta. */
  service: Service;
  /** True si respondió el health-check (Postgres `SELECT 1` / Redis `PING`). */
  up: boolean;
  /** Latencia del check en milisegundos (se renderiza con `tabular-nums`). */
  latencyMs: number;
  /** Resultado textual del check (`SELECT 1 · pgvector OK`, `PING → PONG`, …). */
  detail: string;
  /** ISO del último check, para el "hace N min". */
  checkedAt: string;
  className?: string;
};

/** Metadatos de presentación por servicio (label + descripción del check). */
const SERVICE_META: Record<Service, { label: string; probe: string }> = {
  postgres: { label: "PostgreSQL", probe: "SELECT 1 + pgvector" },
  redis: { label: "Redis", probe: "PING" },
};

/**
 * Estado de un servicio de infra (Postgres / Redis) — blueprint §2.3 / §3 F1.6.
 *
 * Mapeo de estado **decisión de marca**: OK = **azul plano** (NO verde; el panel
 * no tiene token de success), down = `--color-error`. El dot, el label de estado
 * y el borde de acento comparten ese color.
 *
 * Latencia y timestamp van con `tabular-nums`. El "hace N min" se calcula en
 * client (`useEffect`) para evitar mismatch de hidratación: en SSR mostramos el
 * placeholder y el valor real aparece tras montar.
 */
export function StatusCard({ service, up, latencyMs, detail, checkedAt, className }: Props) {
  const meta = SERVICE_META[service];
  // OK = azul plano; down = error. Un solo token gobierna dot + label + acento.
  const statusVar = up ? "--color-blue-flat" : "--color-error";
  const statusLabel = up ? "Operativo" : "Caído";
  const relative = useRelativeTime(checkedAt);

  return (
    <Card className={cn("flex flex-col gap-5", className)}>
      <header className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-caption text-[var(--color-ink-soft)]">{meta.probe}</p>
          <h3 className="text-subtitle text-[var(--color-ink-deep)]">{meta.label}</h3>
        </div>

        {/* Pill de estado: dot + label, ambos en el color del estado. */}
        <span className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1">
          <span
            aria-hidden
            className={cn("size-2 rounded-[var(--radius-pill)]", up && "anim-pulse-soft")}
            style={{ backgroundColor: `var(${statusVar})` }}
          />
          <span className="text-caption" style={{ color: `var(${statusVar})` }}>
            {statusLabel}
          </span>
        </span>
      </header>

      <div className="flex items-baseline gap-2">
        <span className="text-display tabular-nums text-[var(--color-ink-deep)]">
          {fmtMs(latencyMs)}
        </span>
        <span className="text-caption text-[var(--color-ink-soft)]">latencia</span>
      </div>

      <dl className="flex flex-col gap-2 border-t border-[var(--color-border)] pt-4">
        <div className="flex items-center justify-between gap-4">
          <dt className="text-body-sm text-[var(--color-ink-soft)]">Resultado</dt>
          <dd className="text-body-sm tabular-nums text-[var(--color-ink)]">{detail}</dd>
        </div>
        <div className="flex items-center justify-between gap-4">
          <dt className="text-body-sm text-[var(--color-ink-soft)]">Último check</dt>
          <dd className="text-body-sm tabular-nums text-[var(--color-ink)]">{relative}</dd>
        </div>
      </dl>
    </Card>
  );
}

/**
 * Devuelve el "hace N min" de un ISO, calculado en client para no romper la
 * hidratación (en SSR `Date.now()` difiere del cliente). Antes de montar
 * devuelve un guion; tras montar, el valor relativo real.
 */
function useRelativeTime(iso: string): string {
  const [label, setLabel] = useState("—");
  useEffect(() => {
    setLabel(relativeTime(new Date(iso).getTime()));
  }, [iso]);
  return label;
}
