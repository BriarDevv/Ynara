"use client";

import { GrainOverlay, MemoryField } from "@ynara/ui";
import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { Toast } from "@/components/ui/Toast";
import { useUserStore } from "@/stores/user";
import { HoyHeader } from "./HoyHeader";
import { OfflineBanner } from "./OfflineBanner";
import { PrioritiesSection } from "./PrioritiesSection";
import { RecapSection } from "./RecapSection";
import { SuggestionsSection } from "./SuggestionsSection";

// Máscara que desvanece el tint de modo de arriba hacia abajo (sólo un wash
// editorial en el header, no un fondo pleno).
const TINT_FADE: CSSProperties = {
  maskImage: "linear-gradient(to bottom, black, transparent)",
  WebkitMaskImage: "linear-gradient(to bottom, black, transparent)",
};

/** Modo activo de Hoy: el primer modo de interés válido, o productividad. */
function useActiveMode(): ModeId {
  const interestedModes = useUserStore((s) => s.interestedModes);
  return useMemo<ModeId>(() => {
    const first = interestedModes.find((m) => m in MODE_BY_ID);
    return first ?? "productividad";
  }, [interestedModes]);
}

/**
 * Vista **Hoy** — la home real de la app (wireframe 06, build-plan Fase E):
 * header + Prioridades + Sugerencias + Recap, con un wash tintado por el modo
 * activo (la "variante por modo" de los wireframes 13/16) y el banner offline.
 * El modo es display-only hasta la Fase H1 (el switcher es un sheet), así que
 * el tint refleja el modo primario del onboarding.
 *
 * El modo y el nombre salen del onboarding (`useUserStore`); `now` se fija una
 * vez por montaje para anclar la fecha del header sin drift.
 */
export function HoyView() {
  const displayName = useUserStore((s) => s.displayName);
  const activeMode = useActiveMode();
  const [now] = useState(() => new Date());

  // Toast de bienvenida tras el onboarding (`CelebrationOutro` navega a
  // `/hoy?welcome=true`): una sola vez, limpiando el query param sin recargar.
  // Usamos window.location en vez de useSearchParams para no forzar un Suspense
  // boundary y mantener la página prerenderizable.
  const [showWelcome, setShowWelcome] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("welcome") === "true") {
      setShowWelcome(true);
      params.delete("welcome");
      const qs = params.toString();
      window.history.replaceState(null, "", qs ? `/hoy?${qs}` : "/hoy");
    }
  }, []);

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Ambiente de marca (§2/§3.6) detrás del contenido, full-bleed dentro del
          área de scroll del shell. El wash de modo va arriba, desvaneciéndose. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div
          className={`absolute inset-x-0 top-0 h-72 opacity-[0.12] ${MODE_BY_ID[activeMode].gradientClass}`}
          style={TINT_FADE}
        />
        <MemoryField density="dispersa" />
        <GrainOverlay />
      </div>

      <div className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-8 px-6 pb-8 pt-10">
        <OfflineBanner />
        <HoyHeader displayName={displayName} activeMode={activeMode} now={now} />
        <PrioritiesSection />
        <SuggestionsSection />
        <RecapSection />

        <Toast
          message="Listo, ya podés arrancar."
          visible={showWelcome}
          onDismiss={() => setShowWelcome(false)}
          variant="success"
        />
      </div>
    </div>
  );
}
