import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock del cliente HTTP: solo necesitamos api.post; ApiError real para el
// instanceof del onError.
const post = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { post } };
});

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const { ApiError } = await import("@/lib/api");
const { useUserStore } = await import("@/stores/user");
const { useOnboardingStore } = await import("../store");
const { useCompleteOnboarding } = await import("./useCompleteOnboarding");

function wrapper({ children }: { children: React.ReactNode }) {
  // retry: false — convención del repo para tests de hooks de data.
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function seedDraft({ auth }: { auth: "ephemeral" | "signup" | null }) {
  const ob = useOnboardingStore.getState();
  ob.reset();
  ob.setDisplayName("Mateo");
  ob.setMood(["tranquilo"], "");
  ob.setInterestedModes(["productividad"]);
  if (auth) ob.setAuth({ userId: "u1", token: "t1", mode: auth });
}

beforeEach(() => {
  post.mockReset();
  replace.mockClear();
  useUserStore.getState().reset();
  useOnboardingStore.getState().reset();
});

describe("useCompleteOnboarding", () => {
  it("éxito: postea, flipea onboardingCompleted y deriva isEphemeral del authMode", async () => {
    seedDraft({ auth: "ephemeral" });
    post.mockResolvedValue({ ok: true });

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.isCelebrating).toBe(true));
    expect(post).toHaveBeenCalledWith(
      "/v1/user/onboard",
      expect.objectContaining({ displayName: "Mateo", interestedModes: ["productividad"] }),
    );
    expect(useUserStore.getState().onboardingCompleted).toBe(true);
    expect(useUserStore.getState().isEphemeral).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("cuenta registrada (signup): isEphemeral queda en false", async () => {
    seedDraft({ auth: "signup" });
    post.mockResolvedValue({ ok: true });
    // Forzamos el previo a true para que el assert distinga "seteado a false"
    // de "nunca tocado" (no tautológico).
    useUserStore.getState().setAuth({ userId: "x", token: "x", isEphemeral: true });

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.isCelebrating).toBe(true));
    expect(useUserStore.getState().isEphemeral).toBe(false);
  });

  it("sin auth en el draft: error 'Sesión inválida' y NO completa el onboarding", async () => {
    seedDraft({ auth: null });
    post.mockResolvedValue({ ok: true });

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.error).toMatch(/sesión inválida/i));
    expect(useUserStore.getState().onboardingCompleted).toBe(false);
    expect(result.current.isCelebrating).toBe(false);
    // Documenta el gap del audit: el guard de auth vive en onSuccess, así que
    // el POST igual corre antes de detectar la sesión inválida.
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("ApiError: mapea body.detail al mensaje de error y no completa", async () => {
    seedDraft({ auth: "ephemeral" });
    post.mockRejectedValue(new ApiError(500, { detail: "Backend caído" }));

    const { result } = renderHook(() => useCompleteOnboarding(), { wrapper });
    act(() => result.current.complete());

    await waitFor(() => expect(result.current.error).toBe("Backend caído"));
    expect(useUserStore.getState().onboardingCompleted).toBe(false);
  });
});
