import { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, View } from "react-native";
import { OptionCard } from "@/components/ui/OptionCard";
import { Textarea } from "@/components/ui/Textarea";
import { useOnboardingStore } from "@/stores/onboarding";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { MAX_MOOD, MOOD_OPTIONS, STEP_COPY } from "../constants";
import { useOnboardingNav } from "../useOnboardingNav";

const FREE_TEXT_MAX = 160;

export function MoodStep() {
  const copy = STEP_COPY.dia;
  const { next, back } = useOnboardingNav();
  const draftMood = useOnboardingStore((s) => s.mood);
  const draftFreeText = useOnboardingStore((s) => s.moodFreeText);
  const setMood = useOnboardingStore((s) => s.setMood);

  const [selected, setSelected] = useState<string[]>(draftMood);
  const [freeText, setFreeText] = useState(draftFreeText);

  const limitReached = selected.length >= MAX_MOOD;

  // Anuncia al lector de pantalla cuando se llega al máximo (las cards no
  // elegidas quedan disabled y salen del orden de foco). Espeja el live-region
  // `role="status" aria-live="polite"` del MoodStep web; announceForAccessibility
  // funciona en iOS y Android. Solo en la transición a "lleno" — no en mount,
  // así reabrir el paso con 2 moods ya elegidos no dispara un anuncio espurio.
  const wasLimitReached = useRef(limitReached);
  useEffect(() => {
    if (limitReached && !wasLimitReached.current) {
      AccessibilityInfo.announceForAccessibility("Llegaste al máximo de 2 opciones.");
    }
    wasLimitReached.current = limitReached;
  }, [limitReached]);

  const toggle = (value: string) => {
    if (selected.includes(value)) {
      setSelected(selected.filter((v) => v !== value));
    } else if (!limitReached) {
      setSelected([...selected, value]);
    }
  };

  const onNext = () => {
    setMood(selected, freeText.trim());
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
        {MOOD_OPTIONS.map((opt) => {
          const isSelected = selected.includes(opt.value);
          return (
            <OptionCard
              key={opt.value}
              title={opt.label}
              hint={opt.hint}
              selected={isSelected}
              disabled={!isSelected && limitReached}
              onPress={() => toggle(opt.value)}
            />
          );
        })}
      </View>
      <Textarea
        label="ALGO MÁS"
        placeholder="Si querés, contame algo más (opcional)"
        maxLength={FREE_TEXT_MAX}
        value={freeText}
        onChangeText={setFreeText}
      />
    </StepShell>
  );
}
