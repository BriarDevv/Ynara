import { useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LivingField } from "@/components/ui/LivingField";
import { ModePickerSheet } from "@/components/ui/ModePickerSheet";
import { useActiveMode } from "@/hooks/useActiveMode";
import { useUserStore } from "@/stores/user";
import { HoyHeader } from "./components/HoyHeader";
import { PrioritiesSection } from "./components/PrioritiesSection";
import { RecapSection } from "./components/RecapSection";
import { SuggestionsSection } from "./components/SuggestionsSection";

/**
 * Pantalla **Hoy** (mobile) — la home real post-onboarding (wireframe 06):
 * header + Prioridades del día + Sugerencias ("Ynara sugiere") + Recap.
 * Espejo de `HoyView` de web, con el fondo aurora (F3.2); sin el stagger GSAP
 * (flourish exclusivo de web).
 *
 * El modo activo tinta el header y sale del store de modo global
 * (`useActiveMode`): el override del selector, o el primer modo del onboarding.
 * Tocar el chip de modo abre el selector. `now` se fija una vez por montaje
 * para anclar la fecha del header sin drift.
 */
export function HoyScreen() {
  const displayName = useUserStore((s) => s.displayName);
  const activeMode = useActiveMode();
  const [modePickerOpen, setModePickerOpen] = useState(false);
  const [now] = useState(() => new Date());

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="aurora" />
      <SafeAreaView className="flex-1" edges={["top"]}>
        <ScrollView contentContainerClassName="gap-8 px-6 py-8">
          <HoyHeader
            displayName={displayName}
            activeMode={activeMode}
            onPressMode={() => setModePickerOpen(true)}
            now={now}
          />
          <PrioritiesSection />
          <SuggestionsSection />
          <RecapSection />
        </ScrollView>
        <ModePickerSheet open={modePickerOpen} onClose={() => setModePickerOpen(false)} />
      </SafeAreaView>
    </View>
  );
}
