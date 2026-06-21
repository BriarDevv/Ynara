"use client";

import { Icon, type IconName } from "@ynara/ui";
import Link from "next/link";
import { buildAnticipations } from "../anticipations";
import { useAvisosStore } from "../avisosStore";

/**
 * Hub de accesos rápidos de Hoy (solo mobile): Memoria, Avisos y Buscar
 * estaban enterrados dos niveles dentro de "Tú" en mobile (no hay sidebar
 * peek como en desktop). Memoria es el pilar #2 del producto; este hub le da
 * acceso de primer nivel sin tocar las 4 tabs. En desktop se oculta
 * (`lg:hidden`): el sidebar ya tiene estos peeks.
 */
const TOTAL_AVISOS = buildAnticipations().length;

type HubItem = { href: string; label: string; icon: IconName };

const ITEMS: readonly HubItem[] = [
  { href: "/memoria", label: "Tu memoria", icon: "red" },
  { href: "/avisos", label: "Avisos", icon: "recordatorio" },
  { href: "/buscar", label: "Buscar", icon: "buscar" },
];

export function HoyHub() {
  // Pendientes reactivos del badge de Avisos (misma fuente que el sidebar).
  const resolvedCount = useAvisosStore((s) => s.resolvedIds.size);
  const avisosPending = Math.max(0, TOTAL_AVISOS - resolvedCount);

  return (
    <nav aria-label="Accesos rápidos" className="grid grid-cols-3 gap-2 lg:hidden">
      {ITEMS.map((item) => {
        const isAvisos = item.href === "/avisos";
        const showBadge = isAvisos && avisosPending > 0;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={showBadge ? `${item.label} — ${avisosPending} pendientes` : undefined}
            className="relative flex min-h-[44px] flex-col items-center justify-center gap-1.5 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-glass)] px-2 py-3 text-center backdrop-blur-md transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)]"
          >
            <Icon name={item.icon} size={20} className="text-[var(--color-ink-soft)]" />
            <span className="text-caption text-[var(--color-ink)]">{item.label}</span>
            {showBadge ? (
              <span
                aria-hidden
                className="absolute right-1.5 top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-[var(--color-on-dark)]"
                style={{ backgroundColor: "var(--mode-memoria-fill)" }}
              >
                {avisosPending}
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
