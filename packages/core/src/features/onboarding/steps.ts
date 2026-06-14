/**
 * Estructura de los steps del onboarding, compartida web + mobile (ADR-012).
 * El orden es canónico: la ruta del onboarding usa estos slugs. El copy de
 * cada step es platform-specific y vive en cada app.
 */
export const ONBOARDING_STEPS = ["auth", "nombre", "dia", "modos", "a11y"] as const;

export type OnboardingStep = (typeof ONBOARDING_STEPS)[number];

export const STEP_INDEX: Record<OnboardingStep, number> = ONBOARDING_STEPS.reduce(
  (acc, slug, i) => {
    acc[slug] = i;
    return acc;
  },
  {} as Record<OnboardingStep, number>,
);
