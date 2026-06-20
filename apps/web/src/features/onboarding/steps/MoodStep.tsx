"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, type SubmitHandler, useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { OptionCard } from "@/components/ui/OptionCard";
import { Textarea } from "@/components/ui/Textarea";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { MOOD_OPTIONS, STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { useOnboardingStore } from "../store";

const MAX_MOOD = 2;

const MoodFormSchema = z.object({
  mood: z.array(z.string()).max(MAX_MOOD, "Elegí hasta 2"),
  moodFreeText: z.string().max(160, "Máximo 160 caracteres").optional(),
});

type MoodFormValues = z.infer<typeof MoodFormSchema>;

export function MoodStep() {
  const copy = STEP_COPY.dia;
  const { next, back } = useOnboardingNav("dia");
  const draftMood = useOnboardingStore((s) => s.mood);
  const draftFreeText = useOnboardingStore((s) => s.moodFreeText);
  const setMood = useOnboardingStore((s) => s.setMood);

  const form = useForm<MoodFormValues>({
    resolver: zodResolver(MoodFormSchema),
    defaultValues: {
      mood: draftMood,
      moodFreeText: draftFreeText,
    },
    mode: "onSubmit",
  });

  const onSubmit: SubmitHandler<MoodFormValues> = (values) => {
    setMood(values.mood, values.moodFreeText ?? "");
    next();
  };

  return (
    <StepShell
      eyebrow="Paso 3 — Tu día"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={
        <StepFooter
          onBack={back}
          customNext={
            <Button type="submit" fullWidth form="mood-form" className="sm:w-auto sm:min-w-[220px]">
              Seguir
            </Button>
          }
        />
      }
    >
      <form
        id="mood-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-6"
      >
        <Controller
          control={form.control}
          name="mood"
          render={({ field }) => {
            const selected = field.value;
            const limitReached = selected.length >= MAX_MOOD;
            return (
              <fieldset className="flex flex-col gap-3 border-none p-0">
                <legend className="sr-only">Cómo venís — elegí hasta 2</legend>
                {/* Anuncia al lector de pantalla cuando se alcanza el máximo (las
                    cards no elegidas pasan a disabled y salen del orden de foco). */}
                <p className="sr-only" role="status" aria-live="polite">
                  {limitReached ? "Llegaste al máximo de 2 opciones." : ""}
                </p>
                {MOOD_OPTIONS.map((opt) => {
                  const isSelected = selected.includes(opt.value);
                  const isDisabled = !isSelected && limitReached;
                  return (
                    <OptionCard
                      key={opt.value}
                      title={opt.label}
                      hint={opt.hint}
                      selected={isSelected}
                      disabled={isDisabled}
                      onClick={() => {
                        if (isSelected) {
                          field.onChange(selected.filter((v) => v !== opt.value));
                        } else {
                          if (limitReached) return;
                          field.onChange([...selected, opt.value]);
                        }
                      }}
                    />
                  );
                })}
                {form.formState.errors.mood ? (
                  <p role="alert" className="text-body-sm text-[var(--color-error)]">
                    {form.formState.errors.mood.message}
                  </p>
                ) : null}
              </fieldset>
            );
          }}
        />
        <Textarea
          label="ALGO MÁS"
          placeholder="Si querés, contame algo más (opcional)"
          maxLength={160}
          error={form.formState.errors.moodFreeText?.message}
          {...form.register("moodFreeText")}
        />
      </form>
    </StepShell>
  );
}
