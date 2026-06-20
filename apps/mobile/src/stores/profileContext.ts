import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { asyncStorage } from "@/lib/asyncStorage";

export type Dedication = "estudio" | "trabajo" | "ambos" | "otro";

type ProfileContextState = {
  dedication: Dedication | null;
  studyWhat: string;
  workWhat: string;
  purpose: string;
  interests: string;
};

type ProfileContextActions = {
  setContext: (next: Partial<ProfileContextState>) => void;
  reset: () => void;
};

const initialState: ProfileContextState = {
  dedication: null,
  studyWhat: "",
  workWhat: "",
  purpose: "",
  interests: "",
};

/**
 * Contexto del usuario capturado en el onboarding ("Sobre vos"): a qué se dedica,
 * qué estudia/trabaja, para qué usa Ynara y qué le interesa. Alimenta la memoria/
 * personalización de Ynara. Mobile-only y persistido (AsyncStorage); cuando
 * exista el endpoint del backend, esto se sincroniza ahí — hoy queda local.
 */
export const useProfileContextStore = create<ProfileContextState & ProfileContextActions>()(
  persist(
    (set) => ({
      ...initialState,
      setContext: (next) => set(next),
      reset: () => set(initialState),
    }),
    { name: "ynara.profileContext", storage: createJSONStorage(() => asyncStorage) },
  ),
);
