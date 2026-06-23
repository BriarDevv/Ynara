"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { Toast } from "@/components/ui/Toast";
import { useActiveMode } from "@/hooks/useActiveMode";
import { useUserStore } from "@/stores/user";
import { AnticipationsSection } from "./AnticipationsSection";
import { CheckinSection } from "./CheckinSection";
import { HoyHeader } from "./HoyHeader";
import { HoyHub } from "./HoyHub";
import { OfflineBanner } from "./OfflineBanner";
import { PrioritiesSection } from "./PrioritiesSection";
import { RecapSection } from "./RecapSection";
import { SuggestionsSection } from "./SuggestionsSection";

// El flag de bienvenida sale de `window.location.search`, que no existe en SSR.
// Leerlo vía useSyncExternalStore lo mantiene SSR-safe sin el render extra vacío
// de un useState+useEffect de montaje: el snapshot de server es `false` (matchea
// el HTML del server, sin hydration mismatch en `/hoy?welcome=true`) y el del
// cliente lee el query param real. Sin suscripción: el valor es estático tras
// montar (limpiamos la URL una sola vez, abajo).
const noopSubscribe = () => () => {};
const getWelcomeFromUrl = () =>
  new URLSearchParams(window.location.search).get("welcome") === "true";
const getWelcomeServerSnapshot = () => false;

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
  // `/hoy?welcome=true`): una sola vez, leyendo el query param SSR-safe (sin
  // useSearchParams para no forzar un Suspense boundary ni romper el prerender).
  const welcomeFromUrl = useSyncExternalStore(
    noopSubscribe,
    getWelcomeFromUrl,
    getWelcomeServerSnapshot,
  );
  // El dismiss del toast es estado local que pisa el flag de la URL.
  const [welcomeDismissed, setWelcomeDismissed] = useState(false);
  const showWelcome = welcomeFromUrl && !welcomeDismissed;

  // Limpiar el query param sin recargar, una sola vez, recién en el browser.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("welcome") === "true") {
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

      {/* Entrada del hero (momento-firma GSAP, §16 #7): el header y cada
          sección entran con un stagger sutil. `data-hero-reveal` marca los
          bloques que se revelan; el banner y el toast quedan afuera (uno es
          condicional, el otro es overlay). Sin motion, todo aparece directo. */}
      <HeroReveal className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-8 px-6 pb-8 pt-10">
        <OfflineBanner />
        <div data-hero-reveal>
          <HoyHeader displayName={displayName} activeMode={activeMode} now={now} />
        </div>
        {/* Hub de accesos (mobile): Memoria/Avisos/Buscar, enterrados en "Tú". */}
        <div data-hero-reveal>
          <HoyHub />
        </div>
        <div data-hero-reveal>
          <AnticipationsSection />
        </div>
        <div data-hero-reveal>
          <PrioritiesSection />
        </div>
        <div data-hero-reveal>
          <SuggestionsSection />
        </div>
        <div data-hero-reveal>
          <CheckinSection />
        </div>
        <div data-hero-reveal>
          <RecapSection />
        </div>

        <Toast
          message="Listo, ya podés arrancar."
          visible={showWelcome}
          onDismiss={() => setWelcomeDismissed(true)}
          variant="success"
        />
      </HeroReveal>
    </div>
  );
}
