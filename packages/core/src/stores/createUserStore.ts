import type { Mode } from "@ynara/shared-schemas";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
// Import type-only (se borra en runtime): no genera ciclo porque el store de
// onboarding no importa de `stores`. `Dedication` es la fuente canónica del
// step "sobre-vos"; la reusamos acá para no duplicar la unión.
import type { Dedication } from "../features/onboarding/store";

/**
 * Store del perfil de usuario, compartido web + mobile (ADR-012). El storage
 * del `persist` se inyecta: web pasa un storage sobre `localStorage`, mobile
 * uno sobre `expo-secure-store` (regla #5: el token JWT va a SecureStore).
 *
 * El tipo del modo es `Mode` de @ynara/shared-schemas (la unión canónica
 * mirror de Pydantic), para no acoplar core a tipos de UI de ninguna app.
 */
export type UserProfile = {
  userId: string | null;
  /**
   * Token de sesión. Lo consume el cliente API (configureApi.getToken) para
   * adjuntar `Authorization: Bearer <token>`.
   */
  token: string | null;
  displayName: string;
  isEphemeral: boolean;
  /** Resultado del step de mood. */
  mood: string[];
  moodFreeText: string;
  /** Modos elegidos en el onboarding. */
  interestedModes: Mode[];
  /**
   * Contexto del step "sobre-vos" (a qué se dedica, qué estudia/trabaja, para
   * qué usa Ynara y qué le interesa). Alimenta la personalización/memoria;
   * todo opcional y client-side (el backend todavía no tiene columnas).
   */
  dedication: Dedication | null;
  studyWhat: string;
  workWhat: string;
  purpose: string;
  interests: string;
  onboardingCompleted: boolean;
  onboardedAt: number | null;
};

type UserActions = {
  setAuth: (input: { userId: string; token: string; isEphemeral: boolean }) => void;
  setDisplayName: (name: string) => void;
  setMood: (mood: string[], freeText: string) => void;
  setInterestedModes: (modes: Mode[]) => void;
  setProfileContext: (ctx: {
    dedication: Dedication | null;
    studyWhat: string;
    workWhat: string;
    purpose: string;
    interests: string;
  }) => void;
  completeOnboarding: () => void;
  reset: () => void;
};

const initialState: UserProfile = {
  userId: null,
  token: null,
  displayName: "",
  isEphemeral: false,
  mood: [],
  moodFreeText: "",
  interestedModes: [],
  dedication: null,
  studyWhat: "",
  workWhat: "",
  purpose: "",
  interests: "",
  onboardingCompleted: false,
  onboardedAt: null,
};

/**
 * Crea el store de usuario sobre el `storage` provisto. Cada app lo instancia
 * una vez con el storage de su plataforma.
 */
export function createUserStore(storage: StateStorage) {
  return create<UserProfile & UserActions>()(
    persist(
      (set) => ({
        ...initialState,
        setAuth: ({ userId, token, isEphemeral }) => set({ userId, token, isEphemeral }),
        setDisplayName: (displayName) => set({ displayName }),
        setMood: (mood, moodFreeText) => set({ mood, moodFreeText }),
        setInterestedModes: (interestedModes) => set({ interestedModes }),
        setProfileContext: (ctx) => set(ctx),
        completeOnboarding: () => set({ onboardingCompleted: true, onboardedAt: Date.now() }),
        reset: () => set(initialState),
      }),
      { name: "ynara.user", storage: createJSONStorage(() => storage) },
    ),
  );
}
