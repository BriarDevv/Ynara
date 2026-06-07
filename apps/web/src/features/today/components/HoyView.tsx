"use client";

import { useEffect, useState } from "react";
import { LivingField } from "@/components/ui/LivingField";
import { Toast } from "@/components/ui/Toast";
import { useActiveMode } from "@/hooks/useActiveMode";
import { useUserStore } from "@/stores/user";
import { HoyHeader } from "./HoyHeader";
import { OfflineBanner } from "./OfflineBanner";
import { PrioritiesSection } from "./PrioritiesSection";
import { RecapSection } from "./RecapSection";
import { SuggestionsSection } from "./SuggestionsSection";

/**
 * Vista **Hoy** — la home real de la app (wireframe 06, build-plan Fase E):
 * header + Prioridades + Sugerencias + Recap. El fondo es el campo vivo
 * (`LivingField`, variante `aurora`: ondas que fluyen + atmósfera, DESIGN.md
 * §2.2), teñido por el modo activo del usuario.
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
      {/* Fondo vivo de Hoy (aurora): vive absolute dentro del área de scroll
          del shell — nunca fixed, que se escapa del stacking `isolate` del
          AppShell (DESIGN.md §16 #5). */}
      <LivingField variant="aurora" modeId={activeMode} />

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
