"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import type { AdminUsersOutT } from "@/features/users/schemas";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/time";

type Signup = AdminUsersOutT["signups"][number];
type SortKey = "date" | "count";
type SortDir = "asc" | "desc";

type Props = {
  signups: AdminUsersOutT["signups"];
  className?: string;
};

/** Glifo de orden de la columna activa (asc ▲ / desc ▼). */
const SORT_GLYPH: Record<SortDir, string> = { asc: "▲", desc: "▼" };

/**
 * F1.2 · Banda 3 — Altas por día (`users.created_at`).
 *
 * Tabla editorial densa (filas ~40px) sin cajas ni zebra: las filas se separan
 * por hairlines (`divide-y`), el header es sticky y `text-caption uppercase`, y
 * todo conteo/fecha va en `tabular-nums`. Ordenable por fecha o por cantidad
 * (click en el header); el default es fecha descendente (lo más reciente
 * arriba). Client component por el estado de orden.
 */
export function SignupsTable({ signups, className }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const rows = useMemo(() => {
    const dir = sortDir === "asc" ? 1 : -1;
    return [...signups].sort((a: Signup, b: Signup) => {
      if (sortKey === "count") return (a.count - b.count) * dir;
      // Comparación lexicográfica de ISO date == comparación cronológica.
      return a.date < b.date ? -1 * dir : a.date > b.date ? 1 * dir : 0;
    });
  }, [signups, sortKey, sortDir]);

  const total = useMemo(() => signups.reduce((sum, s) => sum + s.count, 0), [signups]);

  /** Alterna dirección si la columna ya está activa; si no, la activa en desc. */
  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  /** Header de columna clickeable con indicador de orden accesible. */
  const headerCell = (key: SortKey, label: string, align: "left" | "right") => {
    const active = key === sortKey;
    return (
      <th
        scope="col"
        aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
        className={cn(
          "sticky top-0 z-[var(--z-base)] bg-[var(--color-bg)] py-2",
          align === "right" ? "text-right" : "text-left",
        )}
      >
        <button
          type="button"
          onClick={() => toggleSort(key)}
          className={cn(
            "inline-flex items-center gap-1.5 text-caption text-[var(--color-ink-soft)] outline-none transition-colors duration-[var(--duration-fast)] hover:text-[var(--color-ink)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]",
            align === "right" && "flex-row-reverse",
          )}
        >
          {label}
          <span aria-hidden className="text-[0.625rem] leading-none">
            {active ? SORT_GLYPH[sortDir] : ""}
          </span>
        </button>
      </th>
    );
  };

  if (signups.length === 0) {
    return (
      <Card className={className}>
        <p className="text-body-sm text-[var(--color-ink-soft)]">Sin altas en el rango.</p>
      </Card>
    );
  }

  return (
    <Card className={cn("flex flex-col gap-4", className)}>
      <header className="flex items-baseline justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-caption text-[var(--color-ink-soft)]">Altas por día</p>
          <h2 className="text-subtitle text-[var(--color-ink-deep)]">Nuevos registros</h2>
        </div>
        <p className="text-body-sm tabular-nums text-[var(--color-ink-soft)]">
          {fmtInt(total)} en el rango
        </p>
      </header>

      <div className="max-h-96 overflow-y-auto scrollbar-none">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              {headerCell("date", "Fecha", "left")}
              {headerCell("count", "Altas", "right")}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {rows.map((row) => (
              <tr
                key={row.date}
                className="h-10 transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)]"
              >
                <td className="py-2 text-body-sm tabular-nums text-[var(--color-ink)]">
                  {row.date}
                </td>
                <td className="py-2 text-right text-body-sm tabular-nums text-[var(--color-ink-deep)]">
                  {fmtInt(row.count)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
