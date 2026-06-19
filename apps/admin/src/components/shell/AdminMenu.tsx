"use client";

import { Icon } from "@ynara/ui";
import { useEffect, useRef, useState } from "react";
import { Diamond } from "@/components/ui/Diamond";
import { useLogout } from "@/features/auth/hooks/useLogout";
import { cn } from "@/lib/cn";
import { useAdminStore } from "@/stores/admin";

/**
 * Identidad admin del topbar convertida en **menú de sesión** (fase WIRE): la
 * pill mantiene el Diamond outline + `display_name`, ahora como disclosure que
 * abre un popover con "Cerrar sesión" (`useLogout`). El displayName sale del
 * admin store (lo setea `useLogin` tras `GET /v1/auth/me`).
 *
 * Dropdown accesible mínimo (sin librería): `aria-expanded`/`aria-haspopup` en
 * el trigger, cierre por click afuera y por `Escape`. Se posiciona absoluto bajo
 * el trigger en `z-topbar` para quedar sobre el chrome.
 */
export function AdminMenu() {
  const displayName = useAdminStore((s) => s.displayName);
  const adminLabel = displayName.trim() || "Admin";
  const { logout } = useLogout();

  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Cierre por click afuera + Escape mientras está abierto.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Sesión admin: ${adminLabel}`}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] py-1 pl-2 pr-3 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:border-[var(--color-border-strong)]",
        )}
      >
        <Diamond size={10} color="var(--color-ink-soft)" variant="outline" />
        <span className="text-caption text-[var(--color-ink-soft)]">{adminLabel}</span>
        <Icon name="chevron" size={14} color="var(--color-ink-muted)" />
      </button>

      {open ? (
        <div
          role="menu"
          aria-label="Menú de sesión"
          className="anim-fade-in absolute right-0 top-[calc(100%+0.5rem)] z-[var(--z-topbar)] min-w-[180px] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] p-1 shadow-lifted"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              void logout();
            }}
            className="flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-3 py-2 text-left text-body-sm text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:bg-[var(--color-bg-soft)]"
          >
            <Icon name="atras" size={16} color="var(--color-ink-soft)" />
            Cerrar sesión
          </button>
        </div>
      ) : null}
    </div>
  );
}
