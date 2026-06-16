import type { Mode } from "@ynara/shared-schemas";
import { useState } from "react";
import { ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useUserStore } from "@/stores/user";
import { HoyHeader } from "./components/HoyHeader";
import { PrioritiesSection } from "./components/PrioritiesSection";

/**
 * Pantalla **Hoy** (mobile) — la home real post-onboarding (wireframe 06):
 * header + Prioridades del día. Sugerencias y Recap llegan en la fase siguiente.
 * Espejo de `HoyView` de web, sin el fondo aurora ni el stagger GSAP (flourishes
 * exclusivos de web).
 *
 * El modo activo tinta el header; sale del primer modo elegido en el onboarding
 * (mobile todavía no persiste un "modo activo" como web). `now` se fija una vez
 * por montaje para anclar la fecha del header sin drift.
 */
export function HoyScreen() {
  const displayName = useUserStore((s) => s.displayName);
  const interestedModes = useUserStore((s) => s.interestedModes);
  const activeMode: Mode = interestedModes[0] ?? "productividad";
  const [now] = useState(() => new Date());

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top"]}>
      <ScrollView contentContainerClassName="gap-8 px-6 py-8">
        <HoyHeader displayName={displayName} activeMode={activeMode} now={now} />
        <PrioritiesSection />
      </ScrollView>
    </SafeAreaView>
  );
}
