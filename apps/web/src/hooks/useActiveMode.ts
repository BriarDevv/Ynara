"use client";

import { useMemo } from "react";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { useActiveModeStore } from "@/stores/mode";
import { useUserStore } from "@/stores/user";

/**
 * Modo activo de la app: el primer modo de interés válido elegido en el
 * onboarding, o productividad como default de marca.
 *
 * Promovido desde `HoyView` (era local) porque el fondo vivo lo necesita en
 * más de una vista: tiñe el clima del canvas de Hoy y Memoria (DESIGN.md
 * §2.2). El Chat no lo usa: ahí el modo preciso es el de la sesión
 * (`session.mode`), que el usuario eligió al arrancar la conversación.
 *
 * El filtro `m in MODE_BY_ID` defiende contra basura persistida en
 * `ynara.user` (localStorage editado o versiones viejas del store).
 */
export function useActiveMode(): ModeId {
  // Override manual del sidebar (paridad mockup): si el usuario eligió un modo,
  // gana; si no (`null`), se deriva del onboarding como antes.
  const override = useActiveModeStore((s) => s.mode);
  const interestedModes = useUserStore((s) => s.interestedModes);
  return useMemo<ModeId>(() => {
    if (override && override in MODE_BY_ID) return override;
    const first = interestedModes.find((m) => m in MODE_BY_ID);
    return first ?? "productividad";
  }, [override, interestedModes]);
}
