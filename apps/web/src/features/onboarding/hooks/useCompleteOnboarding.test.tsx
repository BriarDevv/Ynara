import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// La lógica de validación + `PATCH /v1/users/me` (incluido el huso horario) vive
// ahora en `submitOnboarding` (@ynara/core), testeada en core
// (`completion.test.ts`). Acá testeamos lo que aporta el HOOK: el `onSuccess`
// (commit al user store, seed del modo activo, celebración) y el mapeo de
// errores. Por eso mockeamos `submitOnboarding`, NO el cliente HTTP.
const submitOnboarding = vi.fn();
vi.mock("@ynara/core/features/onboarding", async () => {
  const actual = await vi.importActual<typeof import("@ynara/core/features/onboarding")>(
    "@ynara/core/features/onboarding",
  );
  return { ...actual, submitOnboarding: (...args: unknown[]) => submitOnboarding(...args) };
});

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const { ApiError } = await import("@/lib/api");
const { useUserStore } = await import("@/stores/user");
const { useActiveModeStore } = await import("@/stores/mode");
const { useOnboardingStore } = await import("../store");
const { useCompleteOnboarding } = await import("./useCompleteOnboarding");

function wrapper({ children }: { children: React.ReactNode }) {
  // retry: false — convención del repo para tests de hooks de data.
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// El `onSuccess` del hook lee `authedUserId`/`authedToken` del draft para el
// commit al user store; sembramos auth para que no corte ahí.
function seedDraftAuth() {
  const ob = useOnboardingStore.getState();
  ob.reset();
  ob.setDisplayName("Mateo");
  ob.setAuth({ userId: "u1", token: "t1", mode: "signup" });
}

// Lo que `submitOnboarding` devuelve (payload validado por core). El hook lo
// usa para poblar el user store en `onSuccess`.
const parsedData = {
  displayName: "Mateo",
  mood: ["tranquilo"],
  moodFreeText: undefined,
  interestedModes: ["productividad"],
  a11y: { textSize: "md" as const, highContrast: false, motion: "auto" as const },
};

beforeEach(() => {
  submitOnboarding.mockReset();
  replace.mockClear();
  useUserStore.getState().reset();
  useActiveModeStore.getState().reset();
  useOnboardingStore.getState().reset();
});

describe("useCompleteOnboarding", () => {
  it("éxito: submitOnboarding resuelve → flipea onboardingCompleted y setea isCelebrating", async () => {
    seedDraftAuth();
    submitOnboarding.mockResolvedValue(parsedData);

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.isCelebrating).toBe(true));
    expect(submitOnboarding).toHaveBeenCalledTimes(1);
    expect(useUserStore.getState().onboardingCompleted).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("siembra el modo activo global con el primer modo de interés del onboarding", async () => {
    seedDraftAuth();
    // Primario deliberado distinto del default de marca ('productividad') para que
    // el assert distinga "seteado desde el onboarding" de "fallback derivado".
    submitOnboarding.mockResolvedValue({ ...parsedData, interestedModes: ["estudio", "vida"] });

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.isCelebrating).toBe(true));
    expect(useActiveModeStore.getState().mode).toBe("estudio");
  });

  it("ApiError: mapea body.detail al mensaje de error y no completa", async () => {
    seedDraftAuth();
    submitOnboarding.mockRejectedValue(new ApiError(500, { detail: "Backend caído" }));

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.error).toBe("Backend caído"));
    expect(useUserStore.getState().onboardingCompleted).toBe(false);
    expect(result.current.isCelebrating).toBe(false);
  });

  it("Error normal: mapea el message y no completa", async () => {
    seedDraftAuth();
    submitOnboarding.mockRejectedValue(
      new Error("Sesión inválida. Volvé a empezar el onboarding."),
    );

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.error).toMatch(/sesión inválida/i));
    expect(useUserStore.getState().onboardingCompleted).toBe(false);
    expect(result.current.isCelebrating).toBe(false);
  });
});
