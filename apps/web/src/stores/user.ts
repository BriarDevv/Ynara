import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ModeId } from "@/components/ui/modes";

export type UserProfile = {
  userId: string | null;
  displayName: string;
  isEphemeral: boolean;
  /** Resultados del Step 3 — mood. */
  mood: string[];
  moodFreeText: string;
  /** Resultados del Step 4 — modos elegidos. */
  interestedModes: ModeId[];
  onboardingCompleted: boolean;
  onboardedAt: number | null;
};

type UserActions = {
  setAuth: (input: { userId: string; isEphemeral: boolean }) => void;
  setDisplayName: (name: string) => void;
  setMood: (mood: string[], freeText: string) => void;
  setInterestedModes: (modes: ModeId[]) => void;
  completeOnboarding: () => void;
  reset: () => void;
};

const initialState: UserProfile = {
  userId: null,
  displayName: "",
  isEphemeral: false,
  mood: [],
  moodFreeText: "",
  interestedModes: [],
  onboardingCompleted: false,
  onboardedAt: null,
};

export const useUserStore = create<UserProfile & UserActions>()(
  persist(
    (set) => ({
      ...initialState,
      setAuth: ({ userId, isEphemeral }) => set({ userId, isEphemeral }),
      setDisplayName: (displayName) => set({ displayName }),
      setMood: (mood, moodFreeText) => set({ mood, moodFreeText }),
      setInterestedModes: (interestedModes) => set({ interestedModes }),
      completeOnboarding: () => set({ onboardingCompleted: true, onboardedAt: Date.now() }),
      reset: () => set(initialState),
    }),
    { name: "ynara.user" },
  ),
);
