import type { OnboardingStep } from "@ynara/core/features/onboarding";
import { Text } from "react-native";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { STEP_COPY } from "../constants";
import { useOnboardingNav } from "../useOnboardingNav";

/**
 * Step placeholder para los que todavía no están implementados (dia, modos,
 * a11y, auth). Mantiene el flujo navegable (progreso + atrás/seguir) mientras
 * cada step real llega en su propio PR.
 */
export function PlaceholderStep({ step }: { step: OnboardingStep }) {
  const copy = STEP_COPY[step];
  const { next, back, isFirst, isLast } = useOnboardingNav();

  return (
    <StepShell
      eyebrow={copy.eyebrow}
      title={copy.title}
      subtitle={copy.subtitle}
      footer={
        <StepFooter
          onBack={isFirst ? undefined : back}
          onNext={next}
          nextLabel={isLast ? "Terminar" : "Seguir"}
          nextDisabled={isLast}
        />
      }
    >
      <Text className="text-body text-ink-muted">
        Próximamente — este paso llega en un PR siguiente.
      </Text>
    </StepShell>
  );
}
