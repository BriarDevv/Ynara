import type { LoginResult } from "@ynara/core/features/auth";
import { deriveProfileHydration } from "@ynara/core/features/profile";
import { useA11yStore } from "@/stores/a11y";
import { useUserStore } from "@/stores/user";

/**
 * G3b (mobile) — recupera el perfil de un usuario que YA onboardeó al loguear en
 * un dispositivo nuevo, sin rehacer el onboarding. Hidrata el user store + a11y
 * desde el `UserOut` del login con política **gap-fill** (`deriveProfileHydration`
 * de @ynara/core, fuente de verdad compartida con web): solo rellena lo que está
 * vacío/default localmente, nunca pisa un cambio local. Imperativo
 * (getState/setState): corre en el handler del login, no en render.
 *
 * Espeja `recoverProfileFromLogin` de web; la única diferencia de plataforma es
 * que mobile NO aplica la a11y al DOM (no hay `applyA11yClasses`): el a11y store de
 * mobile es memory-only y su aplicación app-wide es un follow-up, así que acá solo
 * se setean los valores. La lógica pura de QUÉ hidratar vive en core (no se duplica).
 */
export function recoverProfileFromLogin(session: LoginResult): void {
  const userStore = useUserStore.getState();
  userStore.setAuth({ userId: session.userId, token: session.token });

  // Se calcula ANTES de aplicar: `local` refleja el estado del dispositivo
  // (vacío/default en uno nuevo → se adopta todo del backend).
  const hydration = deriveProfileHydration({
    local: userStore,
    localA11y: useA11yStore.getState(),
    me: session.user,
  });

  if (hydration.user.displayName !== undefined) {
    userStore.setDisplayName(hydration.user.displayName);
  }
  if (hydration.user.interestedModes !== undefined) {
    userStore.setInterestedModes(hydration.user.interestedModes);
  }

  const a11yStore = useA11yStore.getState();
  if (hydration.a11y.textSize !== undefined) a11yStore.setTextSize(hydration.a11y.textSize);
  if (hydration.a11y.highContrast !== undefined) {
    a11yStore.setHighContrast(hydration.a11y.highContrast);
  }
  if (hydration.a11y.motion !== undefined) a11yStore.setMotion(hydration.a11y.motion);

  // Marca el onboarding como completo (gate del routing en `(tabs)/_layout`). Se
  // usa `setState` directo en vez de `completeOnboarding()` a propósito: esa acción
  // stampea `onboardedAt: Date.now()` —sería la fecha del login en ESTE dispositivo,
  // no la del onboarding real, que el `UserOut` no trae—, así que se deja
  // `onboardedAt` como está (null) en vez de falsear el dato. Espeja web.
  useUserStore.setState({ onboardingCompleted: true });
}
