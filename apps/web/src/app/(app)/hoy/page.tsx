"use client";

import { GrainOverlay, MemoryField } from "@ynara/ui";
import { useEffect, useMemo, useState } from "react";
import { MODES, type ModeId } from "@/components/ui/modes";
import { Toast } from "@/components/ui/Toast";
import { ChatInputDocked } from "@/features/home/components/ChatInputDocked";
import { EmptySessions } from "@/features/home/components/EmptySessions";
import { Greeting } from "@/features/home/components/Greeting";
import { ModeSwitcher } from "@/features/home/components/ModeSwitcher";
import { RecommendationsGrid } from "@/features/home/components/RecommendationsGrid";
import { useUserStore } from "@/stores/user";

const VALID_MODE_IDS = new Set<ModeId>(MODES.map((m) => m.id));

/**
 * Tab **Hoy** — la home real de la app, dentro del app shell (build-plan
 * §3.1 / Fase A). Por ahora es el dashboard interino heredado de la home
 * vacía (saludo + modos + recomendaciones + sesiones + input deshabilitado):
 * la Hoy-dashboard completa (prioridades · sugerencias · recap) se construye
 * en la Fase E.
 *
 * El cierre del onboarding ya no se difiere acá: `CelebrationOutro` flipea el
 * flag al navegar (el guard del grupo `(app)` exige `onboardingCompleted`
 * antes de montar esta vista).
 */
export default function HoyPage() {
  const displayName = useUserStore((s) => s.displayName);
  const mood = useUserStore((s) => s.mood);
  const moodFreeText = useUserStore((s) => s.moodFreeText);
  const interestedModes = useUserStore((s) => s.interestedModes);

  // Modos para el switcher: los elegidos válidos, con fallback a productividad
  // (el onboarding garantiza ≥1, pero protegemos contra un store vacío).
  const modes = useMemo<ModeId[]>(() => {
    const valid = interestedModes.filter((m) => VALID_MODE_IDS.has(m));
    return valid.length > 0 ? valid : ["productividad"];
  }, [interestedModes]);

  const [activeMode, setActiveMode] = useState<ModeId>("productividad");
  const [prefill, setPrefill] = useState("");

  // Sincroniza el modo activo con los modos disponibles una vez que el store
  // hidrata, preservando la elección del usuario si sigue siendo válida.
  useEffect(() => {
    setActiveMode((curr) => (modes.includes(curr) ? curr : (modes[0] ?? "productividad")));
  }, [modes]);

  // Toast de bienvenida (plan §5.7): una sola vez, limpiando el query param
  // sin recargar. Uso window.location en vez de useSearchParams para no
  // forzar un Suspense boundary y mantener la página prerenderizable.
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

  const onPick = (mode: ModeId, prompt: string) => {
    setActiveMode(mode);
    setPrefill(prompt);
  };

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Ambiente de marca (§2/§3.6) detrás del contenido: la "Red de memoria"
          + grano, full-bleed dentro del área de contenido del shell. El
          overflow-hidden vive en esta capa, no en el contenedor que scrollea. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <MemoryField density="dispersa" />
        <GrainOverlay />
      </div>

      <div className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-8 px-6 pb-8 pt-10">
        {/* En mobile el saludo (big type) va full-width arriba del switcher;
            en sm+ comparten fila. */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <Greeting displayName={displayName} mood={mood} moodFreeText={moodFreeText} />
          <ModeSwitcher interestedModes={modes} activeMode={activeMode} onChange={setActiveMode} />
        </div>

        <div className="flex flex-1 flex-col gap-10">
          <RecommendationsGrid interestedModes={modes} onPick={onPick} />
          <EmptySessions />
        </div>

        <ChatInputDocked value={prefill} />

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
