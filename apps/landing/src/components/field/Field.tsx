"use client";

import dynamic from "next/dynamic";
import { useIsDeckRoute } from "@/lib/useDeckRoute";

// El campo es client-only (WebGL). Sin SSR para el canvas.
const CascadeField = dynamic(() => import("./CascadeField"), { ssr: false });

/**
 * Capa de fondo persistente: el CAMPO CASCADA fijo detrás de todo el contenido.
 * Vive de principio a fin; el scroll lo conduce por UN timeline maestro
 * (olas → giro cenital → plano → puntos → tablero → onda tenue) que COMPLETA
 * exactamente donde arranca la sección horizontal (`[data-cascade-end]`).
 * Viñeta y grano dan la textura nocturna sobre el carbón azulado.
 */
export function Field() {
  // En /presentacion el deck monta y conduce su propio campo → no dupliques WebGL.
  if (useIsDeckRoute()) return null;

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
      <div className="absolute inset-0">
        <CascadeField bare endSelector="[data-cascade-end]" />
      </div>
      {/* Legibilidad SIN costuras: el oscurecido vive en la capa FIJA continua
          (no por sección → nunca aparece una línea al scrollear). Oscurece el
          lado izquierdo (donde vive el texto) y deja la derecha limpia para
          que el campo se vea. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(100deg, rgba(8,10,16,0.7) 0%, rgba(8,10,16,0.34) 30%, rgba(8,10,16,0) 56%)",
        }}
      />
      {/* Viñeta muy suave para asentar los bordes (sin tapar el campo). */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(130% 120% at 50% 45%, transparent 72%, rgba(8,9,14,0.4) 100%)",
        }}
      />
      {/* Grano sutil. */}
      <div className="grain absolute inset-0" />
    </div>
  );
}
