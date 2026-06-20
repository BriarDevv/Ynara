"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, type SubmitHandler, useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { MODE_BY_ID } from "@/components/ui/modes";
import { OptionCard } from "@/components/ui/OptionCard";
import { AVAILABLE_MODES } from "@/lib/modes";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { DEFAULT_MODE, STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { ModeSchema } from "../schemas";
import { useOnboardingStore } from "../store";

const ModesFormSchema = z.object({
  interestedModes: z.array(ModeSchema).min(1, "Elegí al menos uno"),
});

type ModesFormValues = z.infer<typeof ModesFormSchema>;

export function ModesStep() {
  const copy = STEP_COPY.modos;
  const { next, back } = useOnboardingNav("modos");
  const draftModes = useOnboardingStore((s) => s.interestedModes);
  const setInterestedModes = useOnboardingStore((s) => s.setInterestedModes);

  // Si el draft está vacío al montar, pre-marcamos DEFAULT_MODE.
  const initialModes =
    draftModes.length === 0 ? [DEFAULT_MODE] : (draftModes as ModesFormValues["interestedModes"]);

  const form = useForm<ModesFormValues>({
    resolver: zodResolver(ModesFormSchema),
    defaultValues: { interestedModes: initialModes },
    mode: "onSubmit",
  });

  // Si arrancamos con default sintético, escribirlo al store para que
  // el resto del flujo lo vea coherente. Sólo al montar.
  // biome-ignore lint/correctness/useExhaustiveDependencies: pre-mark del default es one-shot al montar; no debe re-correr si draftModes/setInterestedModes cambian después.
  useEffect(() => {
    if (draftModes.length === 0) {
      setInterestedModes([DEFAULT_MODE]);
    }
  }, []);

  const onSubmit: SubmitHandler<ModesFormValues> = (values) => {
    setInterestedModes(values.interestedModes);
    next();
  };

  return (
    <StepShell
      eyebrow="Paso 4 — Para qué te sirvo"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={
        <StepFooter
          onBack={back}
          customNext={
            <Button
              type="submit"
              fullWidth
              form="modes-form"
              className="sm:w-auto sm:min-w-[220px]"
            >
              Seguir
            </Button>
          }
        />
      }
    >
      <form
        id="modes-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-6"
      >
        <Controller
          control={form.control}
          name="interestedModes"
          render={({ field }) => {
            const selected = field.value;
            return (
              <fieldset className="flex flex-col gap-3 border-none p-0">
                <legend className="sr-only">Modos que te interesan — elegí al menos uno</legend>
                {AVAILABLE_MODES.map((modeId) => {
                  const descriptor = MODE_BY_ID[modeId];
                  const isSelected = selected.includes(modeId);
                  return (
                    <OptionCard
                      key={modeId}
                      // Dot color del modo como leading — el chip completo con label
                      // duplicaba el title del card. Acá sólo necesitamos la pista
                      // visual de color (tint plano del modo).
                      leading={
                        <span
                          aria-hidden
                          className="h-2.5 w-2.5 rounded-[var(--radius-pill)]"
                          style={{ backgroundColor: descriptor.tintVar }}
                        />
                      }
                      title={descriptor.label}
                      hint={descriptor.blurb}
                      selected={isSelected}
                      onClick={() => {
                        if (isSelected) {
                          field.onChange(selected.filter((v) => v !== modeId));
                        } else {
                          field.onChange([...selected, modeId]);
                        }
                      }}
                    />
                  );
                })}
                {form.formState.errors.interestedModes ? (
                  <p role="alert" className="text-body-sm text-[var(--color-error)]">
                    {form.formState.errors.interestedModes.message}
                  </p>
                ) : null}
              </fieldset>
            );
          }}
        />
      </form>
    </StepShell>
  );
}
