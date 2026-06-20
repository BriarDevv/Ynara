import type { TextSize } from "@ynara/core/stores";
import { View } from "react-native";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { Toggle } from "@/components/ui/Toggle";
import { useA11yStore } from "@/stores/a11y";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useCompleteOnboarding } from "../useCompleteOnboarding";
import { useOnboardingNav } from "../useOnboardingNav";

const TEXT_SIZE_OPTIONS: readonly { value: TextSize; label: string }[] = [
  { value: "sm", label: "Chico" },
  { value: "md", label: "Normal" },
  { value: "lg", label: "Grande" },
];

/**
 * Step final del onboarding — preferencias de a11y (mobile). Cada control
 * escribe directo al a11y store. El motion se mapea binario: ON → "reduce",
 * OFF → "auto". "Listo" cierra el onboarding (cierre local por ahora; ver
 * useCompleteOnboarding). Aplicar las prefs app-wide es un follow-up.
 */
export function A11yStep() {
  const copy = STEP_COPY.a11y;
  const { back } = useOnboardingNav();

  const textSize = useA11yStore((s) => s.textSize);
  const highContrast = useA11yStore((s) => s.highContrast);
  const motion = useA11yStore((s) => s.motion);
  const setTextSize = useA11yStore((s) => s.setTextSize);
  const setHighContrast = useA11yStore((s) => s.setHighContrast);
  const setMotion = useA11yStore((s) => s.setMotion);

  const { complete } = useCompleteOnboarding();

  return (
    <StepShell
      eyebrow={copy.eyebrow}
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={complete} nextLabel="Listo" />}
    >
      <View className="gap-6">
        <ChipGroup
          label="TAMAÑO DEL TEXTO"
          options={TEXT_SIZE_OPTIONS}
          value={textSize}
          onChange={setTextSize}
        />
        <Toggle
          label="Alto contraste"
          hint="Bordes y textos más definidos."
          checked={highContrast}
          onChange={setHighContrast}
        />
        <Toggle
          label="Reducir animaciones"
          hint="Menos movimiento en transiciones."
          checked={motion === "reduce"}
          onChange={(on) => setMotion(on ? "reduce" : "auto")}
        />
      </View>
    </StepShell>
  );
}
