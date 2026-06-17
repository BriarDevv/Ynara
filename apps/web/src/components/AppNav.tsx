"use client";

import { Icon } from "@ynara/ui";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { MODE_BY_ID, MODES } from "@/components/ui/modes";
import { YnaraWordmark } from "@/components/ui/YnaraWordmark";
import { buildAnticipations } from "@/features/today/anticipations";
import { useActiveMode } from "@/hooks/useActiveMode";
import { cn } from "@/lib/cn";
import { useActiveModeStore } from "@/stores/mode";
import { applyThemeClass, useThemeStore } from "@/stores/theme";
import { useUserStore } from "@/stores/user";
import { isNavItemActive, NAV_ITEMS } from "./nav-items";

/** Cantidad de avisos pendientes (mock; cuando exista el endpoint, sale de ahí). */
const AVISOS_COUNT = buildAnticipations().length;

/**
 * Navegación principal del app shell, en dos chrome por breakpoint
 * (DESIGN.md §12, build-plan §3.1):
 *  - `MobileTabBar` (`<lg`): bottom-tab bar, hermano en flujo del `<main>`
 *    del shell (no fixed) — se ancla abajo en la columna de altura fija sin
 *    tapar el contenido (importa para el composer del chat).
 *  - `SidebarNav` (`lg+`): sidebar a la izquierda, paridad con el `DesktopSidebar`
 *    del mockup — lockup, nav con barra de acento, modos, peeks y footer.
 *
 * Se monta uno por breakpoint con `display:none` (`hidden` / `lg:hidden`):
 * el oculto sale del árbol de accesibilidad, así no hay landmark
 * "Navegación principal" duplicado.
 */

export function MobileTabBar() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Navegación principal"
      className="shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg)]/85 backdrop-blur-md lg:hidden"
    >
      <ul className="mx-auto flex max-w-[640px] items-stretch justify-around px-2 pb-[env(safe-area-inset-bottom)]">
        {NAV_ITEMS.map((item) => {
          const active = isNavItemActive(pathname, item.href);
          return (
            <li key={item.id} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-[56px] flex-col items-center justify-center gap-1 rounded-[var(--radius-md)] py-2 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
                  active
                    ? "text-[var(--color-ink)]"
                    : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]",
                )}
              >
                <Icon name={item.icon} size={24} strokeWidth={active ? 2.6 : 2.2} />
                <span className="text-caption">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Switcher de tema del footer (claro/oscuro). */
function ThemeSwitch() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const OPTIONS = [
    { value: "light", label: "Claro" },
    { value: "dark", label: "Oscuro" },
  ] as const;

  return (
    <div className="mb-2 flex gap-1.5 px-1.5">
      {OPTIONS.map((o) => {
        const on = mounted && theme === o.value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => {
              setTheme(o.value);
              applyThemeClass({ theme: o.value });
            }}
            className={cn(
              "flex-1 rounded-[var(--radius-md)] py-2 text-caption transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
              on
                ? "bg-[var(--color-bg-soft)] text-[var(--color-ink)]"
                : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function SidebarNav() {
  const pathname = usePathname();
  // El lockup se elige por fondo (§11.1): color sobre el sidebar claro,
  // mono-light cuando el tema es Noche. `mounted` evita el hydration mismatch
  // (el server siempre renderiza light, sin localStorage).
  const dark = useThemeStore((s) => s.theme === "dark");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const wordmarkVariant = mounted && dark ? "mono-light" : "color";

  const activeMode = useActiveMode();
  const setMode = useActiveModeStore((s) => s.setMode);
  const accent = MODE_BY_ID[activeMode].tintVar;

  const displayName = useUserStore((s) => s.displayName);
  const initial = displayName.trim().charAt(0).toUpperCase() || "Y";

  return (
    <nav
      aria-label="Navegación principal"
      className="hidden h-full w-[272px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)] lg:flex"
    >
      {/* Lockup oficial (§11.1): símbolo + wordmark con la misma base. El Link
          lleva su propio aria-label, que nombra el control. */}
      <div className="px-[22px] pb-4 pt-5">
        <Link href="/hoy" aria-label="Ynara — ir a Hoy" className="flex w-fit">
          <YnaraWordmark height={30} variant={wordmarkVariant} />
        </Link>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-4 pb-3">
        {/* Nav — indicador por barra fina + acento (sin caja rellena). */}
        <ul className="flex flex-col gap-0.5">
          {NAV_ITEMS.map((item) => {
            const active = isNavItemActive(pathname, item.href);
            return (
              <li key={item.id}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex items-center gap-3 rounded-[var(--radius-md)] py-2.5 pr-2.5 pl-3.5 text-button transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
                    active
                      ? "text-[var(--color-ink)]"
                      : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]",
                  )}
                >
                  {active ? (
                    <span
                      aria-hidden
                      className="absolute top-[9px] bottom-[9px] left-0 w-[3px] rounded-full"
                      style={{ backgroundColor: accent }}
                    />
                  ) : null}
                  <Icon
                    name={item.icon}
                    size={20}
                    strokeWidth={active ? 2.4 : 2}
                    color={active ? accent : undefined}
                  />
                  <span className={cn(active && "font-semibold")}>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>

        {/* Modo · cómo te acompaña — re-tiñe toda la app (useActiveMode). */}
        <div>
          <p className="px-1.5 pb-2 text-caption font-bold uppercase tracking-[0.14em] text-[var(--color-ink-faint)]">
            Modo · cómo te acompaña
          </p>
          <ul className="flex flex-col gap-px">
            {MODES.map((m) => {
              const on = m.id === activeMode;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setMode(m.id)}
                    aria-pressed={on}
                    className="relative flex w-full items-center gap-3 rounded-[var(--radius-md)] py-2 pr-2 pl-3.5 text-left transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]"
                  >
                    {on ? (
                      <span
                        aria-hidden
                        className="absolute top-2 bottom-2 left-0 w-[3px] rounded-full"
                        style={{ backgroundColor: m.tintVar }}
                      />
                    ) : null}
                    <span
                      aria-hidden
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: m.tintVar }}
                    />
                    <span
                      className={cn(
                        "flex-1 text-body-sm",
                        on ? "font-semibold" : "text-[var(--color-ink-soft)]",
                      )}
                      style={on ? { color: m.tintVar } : undefined}
                    >
                      {m.label}
                    </span>
                    {on ? (
                      <span
                        aria-hidden
                        className="h-2 w-2 rotate-45 rounded-[1px]"
                        style={{ backgroundColor: m.tintVar }}
                      />
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Peeks: avisos + memoria + búsqueda. */}
        <div className="flex flex-col">
          {/* Peek "Ynara se adelanta" → /avisos, con badge de pendientes */}
          <Link
            href="/avisos"
            aria-label={`Ynara se adelanta — ${AVISOS_COUNT} avisos pendientes`}
            className="flex items-center gap-3 rounded-[var(--radius-md)] px-2 py-2.5 text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
          >
            <Icon name="recordatorio" size={20} strokeWidth={2} />
            <span className="flex-1 text-body-sm">Ynara se adelanta</span>
            {AVISOS_COUNT > 0 && (
              <span
                aria-hidden
                className="flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 text-[10px] font-bold text-white"
                style={{ backgroundColor: "var(--mode-memoria)" }}
              >
                {AVISOS_COUNT}
              </span>
            )}
            <Icon name="chevron" size={16} strokeWidth={2} />
          </Link>
          <Link
            href="/memoria"
            className="flex items-center gap-3 rounded-[var(--radius-md)] px-2 py-2.5 text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
          >
            <Icon name="red" size={20} strokeWidth={2} />
            <span className="flex-1 text-body-sm">Tu memoria</span>
            <Icon name="chevron" size={16} strokeWidth={2} />
          </Link>
          <Link
            href="/buscar"
            className="flex items-center gap-3 rounded-[var(--radius-md)] px-2 py-2.5 text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
          >
            <Icon name="buscar" size={20} strokeWidth={2} />
            <span className="flex-1 text-body-sm">Buscar</span>
            <Icon name="chevron" size={16} strokeWidth={2} />
          </Link>
        </div>
      </div>

      {/* Footer: tema + perfil. */}
      <div className="border-t border-[var(--color-border)] px-4 py-3">
        <ThemeSwitch />
        <Link
          href="/tu"
          aria-label="Tu perfil"
          className="flex items-center gap-3 rounded-[var(--radius-md)] px-1.5 py-1.5 transition-colors hover:bg-[var(--color-bg-soft)]"
        >
          <span
            aria-hidden
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-body-sm font-semibold text-white"
            // Fill sólido teñido por el modo activo (no gradiente: §3.4 reserva
            // los gradientes al campo vivo / logo / orbe). El `*-fill` es el
            // tono AA-safe del modo, así la inicial blanca contrasta.
            style={{ backgroundColor: MODE_BY_ID[activeMode].fillVar }}
          >
            {initial}
          </span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-body-sm font-semibold text-[var(--color-ink)]">
              {displayName || "Vos"}
            </span>
            <span className="text-caption text-[var(--color-ink-soft)]">Plan gratis</span>
          </span>
          <Icon name="chevron" size={16} strokeWidth={2} />
        </Link>
      </div>
    </nav>
  );
}
