"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { type SubmitHandler, useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { NameFormSchema, type NameFormValues } from "../schemas";
import { useOnboardingStore } from "../store";

export function NameStep() {
  const copy = STEP_COPY.nombre;
  const { next, back } = useOnboardingNav("nombre");
  const displayName = useOnboardingStore((s) => s.displayName);
  const setDisplayName = useOnboardingStore((s) => s.setDisplayName);

  const form = useForm<NameFormValues>({
    resolver: zodResolver(NameFormSchema),
    defaultValues: { displayName },
    mode: "onSubmit",
  });

  const onSubmit: SubmitHandler<NameFormValues> = (values) => {
    setDisplayName(values.displayName.trim());
    next();
  };

  return (
    <StepShell
      title={copy.title}
      subtitle={copy.subtitle}
      footer={
        <StepFooter
          onBack={back}
          customNext={
            <Button type="submit" fullWidth form="name-form" className="sm:w-auto sm:min-w-[200px]">
              Seguir
            </Button>
          }
        />
      }
    >
      <form
        id="name-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-4"
      >
        <TextField
          label="TU NOMBRE"
          placeholder="Ej. Mateo"
          autoFocus
          autoComplete="given-name"
          error={form.formState.errors.displayName?.message}
          {...form.register("displayName")}
        />
      </form>
    </StepShell>
  );
}
