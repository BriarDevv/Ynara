"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/Button";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { Toggle } from "@/components/ui/Toggle";
import { applyA11yClasses, type TextSize, useA11yStore } from "@/stores/a11y";
import { CelebrationOutro } from "../components/CelebrationOutro";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useCompleteOnboarding } from "../hooks/useCompleteOnboarding";
import { useOnboardingNav } from "../hooks/useOnboardingNav";

const TEXT_SIZE_OPTIONS = [
  { value: "sm" as const, label: "Chico" },
  { value: "md" as const, label: "Normal" },
  { value: "lg" as const, label: "Grande" },
];

/**
 * Step final del onboarding — preferencias de a11y.
 *
 * **D3**: cada control escribe directo a `useA11yStore` y dispara
 * `applyA11yClasses` inmediatamente para preview vivo. NO usa el draft
 * `useOnboardingStore.a11y*` (esos campos quedan obsoletos; la fuente
 * canónica de a11y es siempre `useA11yStore`).
 *
 * **Motion toggle**: mapeo binario. OFF (default si OS no pide reduce)
 * → `motion="auto"`. ON (default si OS pide reduce o el user lo elige)
 * → `motion="reduce"`. La opción `"normal"` (forzar animaciones aunque
 * el OS las pida reducidas) NO se expone acá; queda para Ajustes
 * post-MVP donde el user puede pedirlo explícitamente.
 *
 * **Submit**: este es el último step. En vez de `next()`, llama
 * `useCompleteOnboarding.complete()` para cerrar el flujo.
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

  const { complete, isPending, isCelebrating, error, triggerOutroComplete } =
    useCompleteOnboarding();

  // Mapeo motion (tri-estado en store) ⇆ toggle binario.
  // OS-pref se chequea sólo para mostrar el toggle ON cuando motion=auto
  // y el OS pide reduce, así el user ve reflejada la preferencia heredada.
  const osPrefersReduce = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  const motionToggleChecked =
    motion === "reduce" || (motion === "auto" && Boolean(osPrefersReduce));

  const handleTextSize = (value: TextSize) => {
    setTextSize(value);
    applyA11yClasses({ textSize: value, highContrast, motion });
  };

  const handleHighContrast = (on: boolean) => {
    setHighContrast(on);
    applyA11yClasses({ textSize, highContrast: on, motion });
  };

  const handleMotion = (reduceOn: boolean) => {
    const nextMotion = reduceOn ? "reduce" : "auto";
    setMotion(nextMotion);
    applyA11yClasses({ textSize, highContrast, motion: nextMotion });
  };

  // Memoizado: StepFooter recibe JSX por prop; sin memo recibiría un nodo nuevo
  // en cada render y se redibujaría aunque solo cambien otros campos del form.
  // El memo va antes del early-return de `isCelebrating` por rules-of-hooks (no
  // puede ir después); react-doctor lo flaggea pero la posición es obligada.
  // react-doctor-disable-next-line react-doctor/rerender-memo-before-early-return
  const customNext = useMemo(
    () => (
      <Button
        type="button"
        fullWidth
        disabled={isPending}
        onClick={complete}
        className="sm:w-auto sm:min-w-[220px]"
      >
        {isPending ? "Guardando…" : "Listo"}
      </Button>
    ),
    [isPending, complete],
  );

  if (isCelebrating) {
    return <CelebrationOutro onComplete={triggerOutroComplete} />;
  }

  return (
    <StepShell
      eyebrow="Paso 5 — Cómo se lee"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} customNext={customNext} />}
    >
      <div className="flex flex-col gap-6">
        <ChipGroup
          label="TAMAÑO DEL TEXTO"
          options={TEXT_SIZE_OPTIONS}
          value={textSize}
          onChange={handleTextSize}
        />
        <Toggle
          label="Alto contraste"
          hint="Bordes y textos más definidos."
          checked={highContrast}
          onChange={handleHighContrast}
        />
        <Toggle
          label="Reducir animaciones"
          hint="Menos movimiento en transiciones."
          checked={motionToggleChecked}
          onChange={handleMotion}
        />
        {error ? (
          <p role="alert" className="text-body-sm text-[var(--color-error)]">
            {error}
          </p>
        ) : null}
      </div>
    </StepShell>
  );
}
