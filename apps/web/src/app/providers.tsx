"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { shouldEnableMocks } from "@/lib/env";
import { applyA11yClasses, useA11yStore } from "@/stores/a11y";

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
 * Aplica las clases del store de a11y al <html> tras hidratar.
 * Subscribe al store para mantenerlo en sync con cambios en vivo.
 */
function A11yApplier(): null {
  const state = useA11yStore();
  useEffect(() => {
    applyA11yClasses(state);
  }, [state]);
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
      {mocksReady ? children : null}
    </QueryClientProvider>
  );
}
