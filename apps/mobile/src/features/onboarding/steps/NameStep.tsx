import { DisplayNameSchema } from "@ynara/shared-schemas";
import { useState } from "react";
import { TextField } from "@/components/ui/TextField";
import { useOnboardingStore } from "@/stores/onboarding";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../useOnboardingNav";

export function NameStep() {
  const copy = STEP_COPY.nombre;
  const { next, back } = useOnboardingNav();
  const displayName = useOnboardingStore((s) => s.displayName);
  const setDisplayName = useOnboardingStore((s) => s.setDisplayName);

  const [value, setValue] = useState(displayName);
  const [error, setError] = useState<string | undefined>();

  const onNext = () => {
    const parsed = DisplayNameSchema.safeParse(value.trim());
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Revisá tu nombre.");
      return;
    }
    setDisplayName(parsed.data);
    next();
  };

  return (
    <StepShell
      eyebrow={copy.eyebrow}
      title={copy.title}
      subtitle={copy.subtitle}
      // El nombre tiene autoFocus: no le robamos el foco al título.
      focusOnMount={false}
      footer={<StepFooter onBack={back} onNext={onNext} />}
    >
      <TextField
        label="TU NOMBRE"
        placeholder="Ej. Mateo"
        value={value}
        onChangeText={(t) => {
          setValue(t);
          if (error) setError(undefined);
        }}
        autoFocus
        autoComplete="given-name"
        returnKeyType="done"
        onSubmitEditing={onNext}
        error={error}
      />
    </StepShell>
  );
}
