"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { sessionClientStorage } from "@/lib/clientStorage";

/**
 * Flag web-only: marca que el usuario está RE-ABRIENDO el onboarding desde
 * Ajustes (Tú) para completar un perfil que había salteado.
 *
 * Vive fuera del draft del onboarding (que está en @ynara/core, compartido con
 * mobile) para no tocar ese tipo. Persiste en `sessionStorage` —junto al draft—
 * por dos razones:
 *  - sobrevive un refresh a mitad del flujo de resume;
 *  - sobrevive la navegación entre steps, donde `useOnboardingNav.next()` hace
 *    `router.push` sin preservar query params (un `?resume=1` se perdería).
 *
 * El layout de onboarding lo lee para NO redirigir a `/hoy` aunque
 * `onboardingCompleted=true`, y lo limpia al desmontarse (salir del flujo,
 * sea completando o abandonando).
 */
type ResumeState = {
  resuming: boolean;
  setResuming: (value: boolean) => void;
};

export const useOnboardingResumeStore = create<ResumeState>()(
  persist(
    (set) => ({
      resuming: false,
      setResuming: (resuming) => set({ resuming }),
    }),
    {
      name: "ynara.onboarding.resume",
      storage: createJSONStorage(() => sessionClientStorage),
    },
  ),
);
