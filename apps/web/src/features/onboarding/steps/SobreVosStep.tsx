"use client";

import type { Dedication } from "@ynara/core/features/onboarding";
import { useState } from "react";
import { TextField } from "@/components/ui/TextField";
import { cn } from "@/lib/cn";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { useOnboardingStore } from "../store";

const DEDICATION_OPTIONS: readonly { value: Dedication; label: string }[] = [
  { value: "estudio", label: "Estudio" },
  { value: "trabajo", label: "Trabajo" },
  { value: "ambos", label: "Ambos" },
  { value: "otro", label: "Otro" },
];

/**
 * Step "Sobre vos" del onboarding (paso 5): contexto para que Ynara te conozca
 * y lo recuerde (a qué te dedicás, qué estudiás/trabajás, para qué la usás, qué
 * te interesa). Va después de "modos" y antes de "accesibilidad".
 *
 * TODO es opcional: sin validación, el user puede dejar todo en blanco y
 * "Seguir". Como no hay form ni reglas, el estado local se seedea del draft y al
 * avanzar se vuelca con `setProfileContext` (no usamos RHF como los otros steps,
 * que sí validan). `studyWhat` se muestra si dedication es estudio/ambos;
 * `workWhat` si es trabajo/ambos. El draft (core) es la fuente al completar.
 */
export function SobreVosStep() {
  const copy = STEP_COPY["sobre-vos"];
  const { next, back } = useOnboardingNav("sobre-vos");
  const draft = useOnboardingStore.getState();
  const setProfileContext = useOnboardingStore((s) => s.setProfileContext);

  const [dedication, setDedication] = useState<Dedication | null>(draft.dedication);
  const [studyWhat, setStudyWhat] = useState(draft.studyWhat);
  const [workWhat, setWorkWhat] = useState(draft.workWhat);
  const [purpose, setPurpose] = useState(draft.purpose);
  const [interests, setInterests] = useState(draft.interests);

  const showStudy = dedication === "estudio" || dedication === "ambos";
  const showWork = dedication === "trabajo" || dedication === "ambos";

  const onNext = () => {
    setProfileContext({
      dedication,
      studyWhat: studyWhat.trim(),
      workWhat: workWhat.trim(),
      purpose: purpose.trim(),
      interests: interests.trim(),
    });
    next();
  };

  return (
    <StepShell
      eyebrow="Paso 5 — Sobre vos"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} onNext={onNext} nextLabel="Seguir" />}
    >
      <fieldset className="flex flex-col gap-3 border-none p-0">
        {/* Selección única: una fila de pills con aria-pressed (no OptionCard,
            que es para listas largas de una sola columna). */}
        <legend className="text-caption text-[var(--color-ink-soft)]">¿A QUÉ TE DEDICÁS?</legend>
        <div className="flex flex-wrap gap-2">
          {DEDICATION_OPTIONS.map((opt) => {
            const selected = dedication === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                aria-pressed={selected}
                onClick={() => setDedication(opt.value)}
                className={cn(
                  "text-body-sm rounded-[var(--radius-pill)] border px-4 py-2 text-[var(--color-ink)] transition-[border-color,background-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
                  selected
                    ? "border-[var(--color-border-strong)] bg-[var(--color-bg-soft)]"
                    : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]",
                )}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      {showStudy ? (
        <TextField
          label="¿QUÉ ESTUDIÁS?"
          placeholder="Ej. Ingeniería, Medicina…"
          value={studyWhat}
          onChange={(e) => setStudyWhat(e.target.value)}
        />
      ) : null}
      {showWork ? (
        <TextField
          label="¿DE QUÉ TRABAJÁS?"
          placeholder="Ej. Diseño, ventas…"
          value={workWhat}
          onChange={(e) => setWorkWhat(e.target.value)}
        />
      ) : null}

      <TextField
        label="¿PARA QUÉ QUERÉS USAR YNARA?"
        placeholder="Ej. organizarme, estudiar mejor…"
        value={purpose}
        onChange={(e) => setPurpose(e.target.value)}
      />
      <TextField
        label="¿QUÉ ES LO QUE MÁS TE INTERESA?"
        placeholder="Ej. música, programación, deporte…"
        value={interests}
        onChange={(e) => setInterests(e.target.value)}
      />
    </StepShell>
  );
}
