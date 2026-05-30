"use client";

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
 * Home vacío post-onboarding (plan §5). Saludo dinámico, modos elegidos,
 * recomendaciones filtradas por interés, sesiones vacías e input de chat
 * deshabilitado (promesa visual). Backend mockeado: nada persiste todavía.
 *
 * También cierra el onboarding: si llegamos con perfil cargado pero el flag
 * `onboardingCompleted` en false (lo difiere el CelebrationOutro para no
 * romper su animación), lo marcamos acá, ya fuera del árbol del onboarding.
 */
export default function HomePage() {
  const userId = useUserStore((s) => s.userId);
  const displayName = useUserStore((s) => s.displayName);
  const mood = useUserStore((s) => s.mood);
  const moodFreeText = useUserStore((s) => s.moodFreeText);
  const interestedModes = useUserStore((s) => s.interestedModes);
  const completed = useUserStore((s) => s.onboardingCompleted);
  const completeOnboarding = useUserStore((s) => s.completeOnboarding);

  useEffect(() => {
    if (userId && !completed) completeOnboarding();
  }, [userId, completed, completeOnboarding]);

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
      window.history.replaceState(null, "", qs ? `/home?${qs}` : "/home");
    }
  }, []);

  const onPick = (mode: ModeId, prompt: string) => {
    setActiveMode(mode);
    setPrefill(prompt);
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[640px] flex-col gap-8 bg-[var(--color-bg-soft)] px-6 pt-10">
      <div className="flex items-start justify-between gap-4">
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
    </main>
  );
}
