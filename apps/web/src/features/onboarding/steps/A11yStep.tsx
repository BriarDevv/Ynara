"use client";

import { useEffect, useState } from "react";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { Toggle } from "@/components/ui/Toggle";
import { applyA11yClasses, type TextSize, useA11yStore } from "@/stores/a11y";
import { CelebrationOutro } from "../components/CelebrationOutro";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";

const TEXT_SIZE_OPTIONS: readonly { value: TextSize; label: string }[] = [
  { value: "sm", label: "Chico" },
  { value: "md", label: "Normal" },
  { value: "lg", label: "Grande" },
];

/**
 * Step 5 · A11y visual. Tres controles puramente visuales (sin APIs
 * externas) que se aplican en vivo al `<html>` mientras el usuario los
 * toca (plan §4.6). Es el último step: el CTA dispara el outro de
 * celebración en vez de navegar a otro step.
 */
export function A11yStep() {
  const copy = STEP_COPY.a11y;
  const { back } = useOnboardingNav("a11y");

  const textSize = useA11yStore((s) => s.textSize);
  const highContrast = useA11yStore((s) => s.highContrast);
  const motion = useA11yStore((s) => s.motion);
  const setTextSize = useA11yStore((s) => s.setTextSize);
  const setHighContrast = useA11yStore((s) => s.setHighContrast);
  const setMotion = useA11yStore((s) => s.setMotion);

  const [completing, setCompleting] = useState(false);
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    setPrefersReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  // Aplica los cambios al <html> en vivo de forma reactiva: cualquier
  // cambio en el store de a11y re-aplica las clases. Así el efecto es
  // inmediato en la pantalla actual sin depender del orden set→getState.
  useEffect(() => useA11yStore.subscribe(applyA11yClasses), []);

  const onTextSize = (size: TextSize) => setTextSize(size);
  const onHighContrast = (on: boolean) => setHighContrast(on);
  const onReduceMotion = (on: boolean) => setMotion(on ? "reduce" : "normal");

  // El toggle es binario; el store tiene 3 estados. "auto" se muestra como
  // checked si el OS pide reducir movimiento.
  const reduceChecked = motion === "reduce" || (motion === "auto" && prefersReduced);

  if (completing) return <CelebrationOutro />;

  return (
    <StepShell
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={() => setCompleting(true)} nextLabel="Listo" />}
    >
      <div className="flex flex-col gap-8">
        <ChipGroup
          label="TAMAÑO DE TEXTO"
          options={TEXT_SIZE_OPTIONS}
          value={textSize}
          onChange={onTextSize}
        />
        <Toggle
          label="Contraste alto"
          hint="Más definición entre texto y fondo."
          checked={highContrast}
          onChange={onHighContrast}
        />
        <Toggle
          label="Reducir animaciones"
          hint="Menos movimiento en transiciones y efectos."
          checked={reduceChecked}
          onChange={onReduceMotion}
        />
      </div>
    </StepShell>
  );
}
