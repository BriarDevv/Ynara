"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, type SubmitHandler, useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { MODE_BY_ID } from "@/components/ui/modes";
import { OptionCard } from "@/components/ui/OptionCard";
import { AVAILABLE_MODES } from "@/lib/modes";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { ModeSchema } from "../schemas";
import { useOnboardingStore } from "../store";

const ModesFormSchema = z.object({
  interestedModes: z.array(ModeSchema).min(1, "Elegí al menos uno"),
});

type ModesFormValues = z.infer<typeof ModesFormSchema>;

// Estático (sin estado local): se construye una vez a nivel de módulo en vez de
// recrearse cada render, así StepFooter (que recibe JSX por prop) no se redibuja.
const MODES_NEXT_BUTTON = (
  <Button type="submit" fullWidth form="modes-form" className="sm:w-auto sm:min-w-[220px]">
    Seguir
  </Button>
);

export function ModesStep() {
  const copy = STEP_COPY.modos;
  const { next, back } = useOnboardingNav("modos");
  const draftModes = useOnboardingStore((s) => s.interestedModes);
  const setInterestedModes = useOnboardingStore((s) => s.setInterestedModes);

  // Sin pre-pin de un modo por default: arrancamos con lo que haya en el draft
  // (vacío en el primer paso). Así el PRIMER modo que el usuario elige lidera
  // `interestedModes[0]` — y, vía `useActiveMode`, el modo activo de la app. El
  // schema exige `.min(1)`, así que el submit sin elegir nada muestra el error
  // en vez de avanzar con un default sintético ('productividad') que pisaba la
  // intención real del usuario.
  const initialModes = draftModes as ModesFormValues["interestedModes"];

  const form = useForm<ModesFormValues>({
    resolver: zodResolver(ModesFormSchema),
    defaultValues: { interestedModes: initialModes },
    mode: "onSubmit",
  });

  const onSubmit: SubmitHandler<ModesFormValues> = (values) => {
    setInterestedModes(values.interestedModes);
    next();
  };

  return (
    <StepShell
      eyebrow="Paso 4 — Para qué te sirvo"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onBack={back} customNext={MODES_NEXT_BUTTON} />}
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
                      // Falso positivo: OptionCard NO está memoizado (re-renderiza
                      // con el padre igual) y este span es per-item (depende de
                      // descriptor.tintVar del .map): no se puede hoistear ni
                      // envolver en useMemo (hooks no corren dentro del .map).
                      // react-doctor-disable-next-line react-doctor/jsx-no-jsx-as-prop
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
