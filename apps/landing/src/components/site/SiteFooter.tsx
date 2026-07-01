"use client";

import { footer, site } from "@/content/ynara";
import { useIsDeckRoute } from "@/lib/useDeckRoute";

/**
 * Footer hairline — el clímax es la forma + el wordmark «Ynara» (escena de Cierre).
 * Acá sólo una línea fina de legal/meta, opaca, que cierra la página sin competir.
 */
export function SiteFooter() {
  if (useIsDeckRoute()) return null; // el deck cierra con su propia lámina

  return (
    <footer className="relative z-10 border-t border-hair bg-void">
      <div className="shell flex flex-col gap-3 py-6 text-center sm:flex-row sm:items-center sm:justify-between sm:text-left">
        <p className="text-caption">
          © 2026 {site.name} · {site.signoff}
        </p>
        {/* -my-2 compensa el alto extra del py-2 (área táctil ≥44px) para no
            descuadrar la alineación del flex row con los dos <p> meta. */}
        <nav className="-my-2 flex flex-wrap items-center justify-center gap-x-5">
          {footer.columns.map((col) =>
            col.links.map((l) => (
              <a
                key={`${col.title}-${l.label}`}
                href={l.href}
                className="inline-flex items-center py-2 text-caption transition-colors hover:text-text"
              >
                {l.label}
              </a>
            )),
          )}
        </nav>
        <p className="text-caption">{footer.meta}</p>
      </div>
    </footer>
  );
}
