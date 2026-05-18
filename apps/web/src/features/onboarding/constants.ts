import type { ModeId } from "@/components/ui/modes";

/**
 * Orden canónico de los steps. La URL /onboarding/[step] usa estos
 * slugs. Si cambia el orden, hay que actualizar también ProgressDots
 * y el dispatcher de [step]/page.tsx.
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

export const STEP_COPY: Record<OnboardingStep, { title: string; subtitle: string }> = {
  auth: {
    title: "Antes que nada",
    subtitle: "Me hace falta una cuenta para acordarme de vos.",
  },
  nombre: {
    title: "¿Cómo te llamo?",
    subtitle: "Lo uso solo cuando hablo con vos.",
  },
  dia: {
    title: "¿Cómo viene tu día, en general?",
    subtitle: "Elegí lo que aplique. Te voy a entender mejor.",
  },
  modos: {
    title: "¿Para qué te puedo servir?",
    subtitle: "Empezás por lo que te interese. Después abrís más.",
  },
  a11y: {
    title: "Ajustemos cómo se lee.",
    subtitle: "Lo cambiás cuando quieras.",
  },
};

export type MoodOption = {
  value: string;
  label: string;
  hint?: string;
};

export const MOOD_OPTIONS: readonly MoodOption[] = [
  { value: "tranquilo", label: "Tranquilo, con tiempo" },
  { value: "ocupado", label: "Ocupado, varias cosas" },
  { value: "estresado", label: "Estresado" },
  { value: "confuso", label: "Confuso, no sé por dónde arrancar" },
  { value: "creativo", label: "Creativo, con ideas" },
  { value: "cansado", label: "Cansado" },
] as const;

/** Modo pre-marcado por default en Step 4 (modos). */
export const DEFAULT_MODE: ModeId = "productividad";
