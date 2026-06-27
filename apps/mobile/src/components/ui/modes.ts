import type { Mode } from "@ynara/shared-schemas";

/**
 * Descriptores de los modos para la UI mobile (label + blurb). El copy y el
 * orden vienen de la **fuente única** en `@ynara/core/features/modes`, que
 * comparten web/mobile/admin. Mobile sólo agrega su presentación NativeWind
 * (`MODE_DOT_CLASS`). Los consume el onboarding (ModesStep) y el chat (selector
 * + ModeChip).
 */
export { MODE_BY_ID, MODE_DESCRIPTORS, type ModeDescriptor } from "@ynara/core/features/modes";

/**
 * Clase NativeWind del dot/acento por modo. Mapa estático: NativeWind necesita
 * el className literal en build time (no `bg-mode-${id}` dinámico).
 */
export const MODE_DOT_CLASS: Record<Mode, string> = {
  productividad: "bg-mode-productividad",
  estudio: "bg-mode-estudio",
  bienestar: "bg-mode-bienestar",
  vida: "bg-mode-vida",
  memoria: "bg-mode-memoria",
};
