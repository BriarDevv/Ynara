/**
 * Secuencia de pasos del onboarding (mobile). Decoplada de
 * `@ynara/core/features/onboarding` a propósito: así podemos sumar "sobre-vos"
 * (paso 5) sin tocar `packages/core`, que comparte el onboarding con web y se
 * rompería al recibir un step que su UI no conoce. El draft de datos sigue en el
 * store de core; acá vive solo el ORDEN de los pasos.
 */
export const ONBOARDING_STEPS = ["auth", "nombre", "dia", "modos", "sobre-vos", "a11y"] as const;

export type OnboardingStepId = (typeof ONBOARDING_STEPS)[number];

export const STEP_INDEX: Record<OnboardingStepId, number> = ONBOARDING_STEPS.reduce(
  (acc, slug, i) => {
    acc[slug] = i;
    return acc;
  },
  {} as Record<OnboardingStepId, number>,
);
