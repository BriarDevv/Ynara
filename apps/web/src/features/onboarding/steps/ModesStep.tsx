"use client";

import { type CSSProperties, useState } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODES, type ModeId } from "@/components/ui/modes";
import { OptionCard } from "@/components/ui/OptionCard";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { DEFAULT_MODE, STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { ModesFormSchema } from "../schemas";
import { useOnboardingStore } from "../store";

/**
 * Step 4 · Modos. Multi-select con mínimo 1 (plan §4.5). Si el usuario
 * llega sin nada elegido, arranca con {@link DEFAULT_MODE} pre-marcado.
 * Cada card muestra su ModeChip con el tint del modo.
 */
export function ModesStep() {
  const copy = STEP_COPY.modos;
  const { next, back } = useOnboardingNav("modos");
  const storedModes = useOnboardingStore((s) => s.interestedModes);
  const setInterestedModes = useOnboardingStore((s) => s.setInterestedModes);

  const [selected, setSelected] = useState<ModeId[]>(() => {
    const valid = storedModes.filter((m): m is ModeId => MODES.some((mode) => mode.id === m));
    return valid.length > 0 ? valid : [DEFAULT_MODE];
  });
  const [error, setError] = useState<string | null>(null);

  const toggle = (id: ModeId) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]));
    setError(null);
  };

  const handleNext = () => {
    const parsed = ModesFormSchema.safeParse({ interestedModes: selected });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Elegí al menos uno");
      return;
    }
    setInterestedModes(parsed.data.interestedModes);
    next();
  };

  return (
    <StepShell
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={handleNext} />}
    >
      <div className="flex flex-col gap-3">
        <fieldset
          aria-describedby={error ? "modes-error" : undefined}
          className="flex flex-col gap-3 border-0 p-0"
        >
          <legend className="sr-only">Modos que te interesan</legend>
          {MODES.map((mode, i) => (
            // Stagger de entrada (§8.2): fade-up con delay por índice (cap 6)
            // vía --stagger-index; reduced-motion lo neutraliza global (ver MoodStep).
            <div
              key={mode.id}
              className="anim-stagger-up"
              style={{ "--stagger-index": Math.min(i, 5) } as CSSProperties}
            >
              <OptionCard
                title={mode.label}
                hint={mode.blurb}
                selected={selected.includes(mode.id)}
                onClick={() => toggle(mode.id)}
                leading={<ModeChip modeId={mode.id} size="sm" />}
              />
            </div>
          ))}
        </fieldset>
        {error ? (
          <p id="modes-error" role="alert" className="text-body-sm text-[var(--color-error)]">
            {error}
          </p>
        ) : (
          <p className="text-caption text-[var(--color-ink-muted)]">
            Después podés activar más desde Ajustes.
          </p>
        )}
      </div>
    </StepShell>
  );
}
