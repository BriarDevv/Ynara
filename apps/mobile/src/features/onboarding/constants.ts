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
    eyebrow: "Paso 1 — Cuenta",
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
    eyebrow: "Paso 4 — Para qué te sirvo",
    title: "¿Para qué te puedo servir?",
    subtitle: "Empezás por lo que te interese. Después abrís más.",
  },
  a11y: {
    eyebrow: "Paso 5 — Cómo se lee",
    title: "Ajustemos cómo se lee.",
    subtitle: "Lo cambiás cuando quieras.",
  },
};

/** Máximo de moods seleccionables en el step "Tu día" (igual que la web). */
export const MAX_MOOD = 2;

export type MoodOption = {
  value: string;
  label: string;
  hint?: string;
};

// Opciones del step "Tu día" — verbatim de apps/web/.../onboarding/constants.ts.
export const MOOD_OPTIONS: readonly MoodOption[] = [
  { value: "tranquilo", label: "Tranquilo, con tiempo" },
  { value: "ocupado", label: "Ocupado, varias cosas" },
  { value: "estresado", label: "Estresado" },
  { value: "confuso", label: "Confuso, no sé por dónde arrancar" },
  { value: "creativo", label: "Creativo, con ideas" },
  { value: "cansado", label: "Cansado" },
] as const;
