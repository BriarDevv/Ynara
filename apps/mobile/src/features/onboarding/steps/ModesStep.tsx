import { useEffect, useState } from "react";
import { View } from "react-native";
import { OptionCard } from "@/components/ui/OptionCard";
import { Text } from "@/components/ui/Text";
import { useOnboardingStore } from "@/stores/onboarding";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { DEFAULT_MODE, MODE_DOT_CLASS, MODE_OPTIONS } from "../modes";
import { useOnboardingNav } from "../useOnboardingNav";

export function ModesStep() {
  const copy = STEP_COPY.modos;
  const { next, back } = useOnboardingNav();
  const draftModes = useOnboardingStore((s) => s.interestedModes);
  const setInterestedModes = useOnboardingStore((s) => s.setInterestedModes);

  // Si el draft está vacío, pre-marcamos el modo default (igual que la web).
  const [selected, setSelected] = useState<string[]>(
    draftModes.length === 0 ? [DEFAULT_MODE] : draftModes,
  );
  const [error, setError] = useState<string | undefined>();

  // Persistir el default sintético al store en el primer montaje.
  // biome-ignore lint/correctness/useExhaustiveDependencies: one-shot al montar.
  useEffect(() => {
    if (draftModes.length === 0) setInterestedModes([DEFAULT_MODE]);
  }, []);

  const toggle = (id: string) => {
    setError(undefined);
    setSelected((curr) => (curr.includes(id) ? curr.filter((v) => v !== id) : [...curr, id]));
  };

  const onNext = () => {
    if (selected.length === 0) {
      setError("Elegí al menos uno");
      return;
    }
    setInterestedModes(selected);
    next();
  };

  return (
    <StepShell
      eyebrow={copy.eyebrow}
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={onNext} />}
    >
      <View className="gap-3">
        {MODE_OPTIONS.map((mode) => (
          <OptionCard
            key={mode.id}
            title={mode.label}
            hint={mode.blurb}
            selected={selected.includes(mode.id)}
            onPress={() => toggle(mode.id)}
            leading={<View className={`h-2.5 w-2.5 rounded-pill ${MODE_DOT_CLASS[mode.id]}`} />}
          />
        ))}
        {error ? <Text className="text-body-sm text-error">{error}</Text> : null}
      </View>
    </StepShell>
  );
}
