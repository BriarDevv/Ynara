import { ONBOARDING_STEPS, type OnboardingStep, STEP_INDEX } from "@ynara/core/features/onboarding";
import type { ModeId } from "@/components/ui/modes";

export type { OnboardingStep };
// La estructura de steps (orden, índice, tipo) se movió a @ynara/core (ADR-012)
// para compartirla con mobile. Se re-exporta acá para no tocar los call-sites
// que importan desde "../constants". El copy de cada step es web-specific y
// se queda en este archivo.
export { ONBOARDING_STEPS, STEP_INDEX };

export const STEP_COPY: Record<OnboardingStep, { title: string; subtitle: string }> = {
  auth: {
    title: "Antes que nada",
    subtitle:
      "Me hace falta una cuenta para acordarme de vos. Tu memoria es tuya, cifrada y exportable — y no se manda a IA de terceros.",
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

/**
 * Copy específico de los dos modos visuales del step `auth` (signup y
 * login). `STEP_COPY.auth` mantiene el copy de signup por compatibilidad
 * con el header. `LoginForm` lee desde `AUTH_STEP_COPY.login`.
 */
export const AUTH_STEP_COPY = {
  signup: STEP_COPY.auth,
  login: {
    title: "Bienvenido de vuelta",
    subtitle: "Ingresá con tu cuenta existente.",
  },
} as const;

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
