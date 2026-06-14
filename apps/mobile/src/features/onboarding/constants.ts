import type { OnboardingStep } from "@ynara/core/features/onboarding";

/**
 * Copy de cada step del onboarding (mobile). El mismo tono que la web
 * (apps/web/src/features/onboarding/constants.ts); el copy es platform-specific
 * (la UI difiere), así que vive en cada app.
 */
export const STEP_COPY: Record<
  OnboardingStep,
  { eyebrow: string; title: string; subtitle: string }
> = {
  auth: {
    eyebrow: "Paso 1 — Tu cuenta",
    title: "Antes que nada",
    subtitle: "Me hace falta una cuenta para acordarme de vos.",
  },
  nombre: {
    eyebrow: "Paso 2 — Tu nombre",
    title: "¿Cómo te llamo?",
    subtitle: "Lo uso solo cuando hablo con vos.",
  },
  dia: {
    eyebrow: "Paso 3 — Tu día",
    title: "¿Cómo viene tu día, en general?",
    subtitle: "Elegí lo que aplique. Te voy a entender mejor.",
  },
  modos: {
    eyebrow: "Paso 4 — Para qué",
    title: "¿Para qué te puedo servir?",
    subtitle: "Empezás por lo que te interese. Después abrís más.",
  },
  a11y: {
    eyebrow: "Paso 5 — Cómo se lee",
    title: "Ajustemos cómo se lee.",
    subtitle: "Lo cambiás cuando quieras.",
  },
};
