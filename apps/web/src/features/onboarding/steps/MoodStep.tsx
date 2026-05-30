"use client";

import { useState } from "react";
import { OptionCard } from "@/components/ui/OptionCard";
import { Textarea } from "@/components/ui/Textarea";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { MOOD_OPTIONS, STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { MAX_MOOD_FREE_TEXT, MAX_MOODS, MoodFormSchema } from "../schemas";
import { useOnboardingStore } from "../store";

/**
 * Step 3 · Día (mood). Multi-select limitado a {@link MAX_MOODS} +
 * textarea libre opcional. Sin mínimo: el usuario puede seguir sin
 * elegir nada (plan §4.4). Alimenta la primera memoria episódica.
 */
export function MoodStep() {
  const copy = STEP_COPY.dia;
  const { next, back } = useOnboardingNav("dia");
  const storedMood = useOnboardingStore((s) => s.mood);
  const storedFreeText = useOnboardingStore((s) => s.moodFreeText);
  const setMood = useOnboardingStore((s) => s.setMood);

  const [selected, setSelected] = useState<string[]>(storedMood);
  const [freeText, setFreeText] = useState(storedFreeText);

  const atLimit = selected.length >= MAX_MOODS;

  const toggle = (value: string) => {
    setSelected((prev) => {
      if (prev.includes(value)) return prev.filter((v) => v !== value);
      if (prev.length >= MAX_MOODS) return prev;
      return [...prev, value];
    });
  };

  const handleNext = () => {
    // El límite de moods y de caracteres ya lo fuerza la UI; validamos
    // igual contra el schema para no persistir un draft inconsistente
    // (mismo patrón que ModesStep). Si fallara, recortamos al límite.
    const parsed = MoodFormSchema.safeParse({ mood: selected, moodFreeText: freeText.trim() });
    const data = parsed.success
      ? parsed.data
      : {
          mood: selected.slice(0, MAX_MOODS),
          moodFreeText: freeText.trim().slice(0, MAX_MOOD_FREE_TEXT),
        };
    setMood(data.mood, data.moodFreeText);
    next();
  };

  return (
    <StepShell
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={handleNext} />}
    >
      <div className="flex flex-col gap-3">
        <fieldset className="grid gap-3 border-0 p-0 sm:grid-cols-2">
          <legend className="sr-only">Cómo viene tu día</legend>
          {MOOD_OPTIONS.map((opt) => {
            const isSelected = selected.includes(opt.value);
            return (
              <OptionCard
                key={opt.value}
                title={opt.label}
                hint={opt.hint}
                selected={isSelected}
                disabled={!isSelected && atLimit}
                onClick={() => toggle(opt.value)}
              />
            );
          })}
        </fieldset>
        <p className="text-caption text-[var(--color-ink-muted)]">
          Hasta {MAX_MOODS}. Podés seguir sin elegir ninguno.
        </p>
      </div>

      <Textarea
        label="ALGO MÁS (OPCIONAL)"
        placeholder="Contame en tus palabras, si querés."
        rows={3}
        maxLength={MAX_MOOD_FREE_TEXT}
        value={freeText}
        onChange={(e) => setFreeText(e.target.value)}
        hint={`${freeText.length}/${MAX_MOOD_FREE_TEXT}`}
      />
    </StepShell>
  );
}
