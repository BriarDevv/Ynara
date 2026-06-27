/**
 * Secuencia de pasos del onboarding (mobile). Ya NO se forkea: la estructura
 * (orden, índice, tipo) vive en `@ynara/core/features/onboarding` y se comparte
 * con web (ADR-012). "sobre-vos" ahora es canónico en core, así que mobile la
 * re-exporta como hace web. Se mantiene el alias `OnboardingStepId` para no
 * tocar los call-sites mobile que ya lo importan (`steps`, `Wizard`, etc.).
 */
import { ONBOARDING_STEPS, type OnboardingStep, STEP_INDEX } from "@ynara/core/features/onboarding";

export { ONBOARDING_STEPS, STEP_INDEX };

export type OnboardingStepId = OnboardingStep;
