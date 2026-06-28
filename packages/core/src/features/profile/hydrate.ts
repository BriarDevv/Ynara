import type { Mode, UserOut } from "@ynara/shared-schemas";
import type { MotionPreference, TextSize } from "../../stores";

/**
 * Hidratación del perfil desde el backend (`me`), compartida web + mobile (G3,
 * ADR-026). Política **conservadora (gap-fill, no clobber)**: el servidor SOLO
 * rellena lo que está vacío/default localmente; nunca pisa un valor que el
 * usuario ya cambió en este dispositivo. Razón: hoy NO hay write-back de
 * `interested_modes`/`a11y` (solo el onboarding los escribe vía POST
 * /v1/onboarding), así que el `me` puede estar más viejo que un cambio local; si
 * el server "ganara" siempre, revertiría ajustes que el usuario hizo después.
 *
 * Caso de uso real (G3b): login en un **dispositivo nuevo**. El user store local
 * arranca vacío y el a11y store en el default, así que todo se adopta del `me`
 * (recuperás tu perfil sin rehacer el onboarding). En el mismo dispositivo
 * (re-login) lo local ya está poblado/customizado y se respeta.
 *
 * `deriveProfileHydration` es **pura** (sin tocar stores): devuelve los parches a
 * aplicar. Cada app los aplica a sus propios stores (web/mobile), porque las
 * instancias de store son platform-specific.
 */

/** Default del a11y store (`createA11yStore`). Si lo local matchea esto, se
 *  considera "sin customizar" y el server puede rellenarlo. */
const DEFAULT_A11Y = {
  textSize: "md" as TextSize,
  highContrast: false,
  motion: "auto" as MotionPreference,
};

/** Snapshot local mínimo del user store que mira la hidratación. */
export type LocalProfileSnapshot = {
  displayName: string;
  interestedModes: Mode[];
  onboardingCompleted: boolean;
};

/** Snapshot local del a11y store. */
export type LocalA11ySnapshot = {
  textSize: TextSize;
  highContrast: boolean;
  motion: MotionPreference;
};

/** Parches a aplicar (campos ausentes = no cambiar). */
export type ProfileHydration = {
  user: Partial<{ displayName: string; interestedModes: Mode[]; onboardingCompleted: boolean }>;
  a11y: Partial<LocalA11ySnapshot>;
};

/**
 * Calcula qué hidratar del `me` respetando lo local (gap-fill). Reglas:
 * - `displayName`: se adopta si lo local está vacío y el server tiene uno.
 * - `interestedModes`: se adopta si lo local está vacío y el server trae ≥1.
 * - `onboardingCompleted`: se marca si el server lo tiene y lo local no (fill-forward,
 *   nunca lo des-marca).
 * - `a11y`: se adopta el bloque completo SOLO si lo local está en el default
 *   (sin customizar) y el server tiene a11y guardada.
 */
export function deriveProfileHydration(args: {
  local: LocalProfileSnapshot;
  localA11y: LocalA11ySnapshot;
  me: UserOut;
}): ProfileHydration {
  const { local, localA11y, me } = args;
  const user: ProfileHydration["user"] = {};

  if (local.displayName === "" && me.display_name) {
    user.displayName = me.display_name;
  }

  const serverModes = me.preferences?.interested_modes;
  if (local.interestedModes.length === 0 && serverModes && serverModes.length > 0) {
    user.interestedModes = serverModes;
  }

  if (!local.onboardingCompleted && me.onboarding_completed) {
    user.onboardingCompleted = true;
  }

  const a11y: ProfileHydration["a11y"] = {};
  const serverA11y = me.preferences?.a11y;
  const localIsDefault =
    localA11y.textSize === DEFAULT_A11Y.textSize &&
    localA11y.highContrast === DEFAULT_A11Y.highContrast &&
    localA11y.motion === DEFAULT_A11Y.motion;
  if (serverA11y && localIsDefault) {
    a11y.textSize = serverA11y.text_size;
    a11y.highContrast = serverA11y.high_contrast;
    a11y.motion = serverA11y.motion;
  }

  return { user, a11y };
}
