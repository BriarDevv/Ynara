"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
// Side-effect import: corre `configureApi` (instala baseUrl + getToken del cliente
// HTTP de @ynara/core) en TODA ruta, ANTES de cualquier request. Sin esto, una ruta
// que solo importa hooks de @ynara/core (p.ej. /hoy → useTasks importa el `api` de
// core, no `@/lib/api`) se carga con el cliente SIN configurar y las requests salen
// sin Authorization (getToken default = () => null) → 401 en un load/reload directo.
// El onboarding/chat/memoria ya lo importaban transitivamente; /hoy y otras no.
import "@/lib/api";
import { shouldEnableMocks } from "@/lib/env";
import { applyA11yClasses, useA11yStore } from "@/stores/a11y";
import { applyThemeClass, useThemeStore } from "@/stores/theme";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

/**
 * Mantiene las clases de a11y del <html> (text-size, alto contraste, motion)
 * en sync con el store. Aplica desde `getState()` + `subscribe`, NO desde el
 * valor renderizado: en el render de hidratación useSyncExternalStore sirve
 * `getInitialState()` (los defaults md/false/auto) aunque persist ya haya
 * rehidratado otra preferencia, y un efecto colgado de ese valor pisaría las
 * clases que el pre-paint (a11y-init.ts) puso antes del primer paint — flash
 * lg→md→lg (issue #182). Con getState() el primer apply ya ve el estado
 * hidratado (persist sobre localStorage rehidrata sincrónico). Mismo patrón
 * que ThemeApplier.
 */
function A11yApplier(): null {
  useEffect(() => {
    applyA11yClasses(useA11yStore.getState());
    return useA11yStore.subscribe((state) =>
      applyA11yClasses({
        textSize: state.textSize,
        highContrast: state.highContrast,
        motion: state.motion,
      }),
    );
  }, []);
  return null;
}

/**
 * Mantiene la clase `theme-dark` y el `data-theme` del <html> en sync
 * con el store de tema. Aplica desde `getState()` + `subscribe`, NO desde
 * el valor renderizado: en el render de hidratación useSyncExternalStore
 * sirve `getInitialState()` (el default "light") aunque persist ya haya
 * rehidratado "dark", y un efecto colgado de ese valor pisaría la clase
 * que el pre-paint (a11y-init.ts) puso antes del primer paint — flash
 * oscuro→claro→oscuro. Con getState() el primer apply ya ve el estado
 * hidratado (persist sobre localStorage rehidrata sincrónico).
 */
function ThemeApplier(): null {
  useEffect(() => {
    applyThemeClass(useThemeStore.getState());
    const unsubscribe = useThemeStore.subscribe((state) => applyThemeClass({ theme: state.theme }));

    // Tema `system`: re-aplicar cuando el SO cambia de claro↔oscuro con la app
    // abierta (solo si la preferencia sigue siendo `system`; con light/dark
    // explícito el cambio del SO no afecta).
    const mql = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onSystemChange = () => {
      if (useThemeStore.getState().theme === "system") {
        applyThemeClass(useThemeStore.getState());
      }
    };
    mql?.addEventListener("change", onSystemChange);

    return () => {
      unsubscribe();
      mql?.removeEventListener("change", onSystemChange);
    };
  }, []);
  return null;
}

/**
 * Inicia el worker MSW en client cuando corresponde. Bloquea el render
 * de children hasta que el worker esté activo, así ningún fetch temprano
 * se escapa sin mock.
 */
function useMockServiceWorker(): boolean {
  const [ready, setReady] = useState(!shouldEnableMocks);
  const started = useRef(false);

  useEffect(() => {
    if (!shouldEnableMocks || started.current) return;
    started.current = true;
    import("@/lib/mocks-browser").then(({ worker }) =>
      worker
        .start({ onUnhandledRequest: "bypass" })
        .then(() => setReady(true))
        .catch((err: unknown) => {
          console.error("[mocks] no se pudo iniciar MSW:", err);
          setReady(true); // dejar pasar igual; mejor app rota que app trabada
        }),
    );
  }, []);

  return ready;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  const mocksReady = useMockServiceWorker();

  return (
    <QueryClientProvider client={client}>
      <A11yApplier />
      <ThemeApplier />
      {mocksReady ? children : null}
    </QueryClientProvider>
  );
}
