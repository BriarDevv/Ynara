"use client";

import { Icon } from "@ynara/ui";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { ApiStatusFooter } from "./ApiStatusFooter";
import { isNavItemActive, NAV_ITEMS } from "./nav-items";

/**
 * Sidebar del panel (blueprint §2.1): nav agrupada en bloques con separador
 * caption uppercase. El item activo lleva una barra de acento izquierda de 3px
 * azul plano + `bg-bg-soft` + `ink-deep` (sin caja rellena — coherente con el
 * web). Lee `usePathname()`.
 *
 * Colapso responsive: en `lg+` es un rail de 248px con labels; por debajo de
 * `lg` colapsa a rail de 64px icon-only (los labels caen a `sr-only` y los
 * separadores de grupo se vuelven un hairline). Las dos anchuras las define el
 * grid de `AdminShell`; acá sólo se ocultan/muestran los labels con `lg:`.
 */
export function Sidebar() {
  const pathname = usePathname();
  const accent = "var(--color-blue-flat)";

  return (
    <nav
      aria-label="Navegación del panel"
      className="flex h-full flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]"
    >
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-2 pb-3 pt-5 lg:px-3">
        {NAV_ITEMS.map((group, gi) => (
          <div key={group.label || `g-${gi}`} className="flex flex-col gap-1">
            {group.label ? (
              <>
                {/* Label visible en rail ancho; hairline separador en rail colapsado. */}
                <p className="hidden px-2.5 pb-1 text-caption text-[var(--color-ink-soft)] lg:block">
                  {group.label}
                </p>
                <div aria-hidden className="mx-2 mb-1 h-px bg-[var(--color-border)] lg:hidden" />
              </>
            ) : null}
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = isNavItemActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      title={item.label}
                      className={cn(
                        "relative flex items-center gap-3 rounded-[var(--radius-md)] py-2.5 pl-3.5 pr-2.5 text-button transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
                        "max-lg:justify-center max-lg:px-0",
                        active
                          ? "bg-[var(--color-bg-soft)] text-[var(--color-ink-deep)]"
                          : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)] hover:bg-[var(--color-bg-soft)]",
                      )}
                    >
                      {active ? (
                        <span
                          aria-hidden
                          className="absolute bottom-[9px] left-0 top-[9px] w-[3px] rounded-full"
                          style={{ backgroundColor: accent }}
                        />
                      ) : null}
                      <Icon
                        name={item.icon}
                        size={20}
                        strokeWidth={active ? 2.4 : 2}
                        color={active ? accent : undefined}
                      />
                      <span className={cn("max-lg:sr-only", active && "font-semibold")}>
                        {item.label}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      {/* Footer del rail: estado de la API (neutro hasta cablear /system). */}
      <div className="border-t border-[var(--color-border)] px-2 py-2 lg:px-3">
        <span className="max-lg:hidden">
          <ApiStatusFooter />
        </span>
        <span className="lg:hidden">
          <ApiStatusFooter collapsed />
        </span>
      </div>
    </nav>
  );
}
