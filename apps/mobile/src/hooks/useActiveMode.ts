import type { Mode } from "@ynara/shared-schemas";
import { useMemo } from "react";
import { MODE_BY_ID } from "@/components/ui/modes";
import { useActiveModeStore } from "@/stores/mode";
import { useUserStore } from "@/stores/user";

/**
 * Modo activo efectivo de la app (F2). Espejo del `useActiveMode` de web: el
 * override manual del selector gana; si no hay (`null`), se deriva del primer
 * modo de interés válido del onboarding, con productividad como default de
 * marca. El filtro `m in MODE_BY_ID` defiende contra basura persistida.
 */
export function useActiveMode(): Mode {
  const override = useActiveModeStore((s) => s.mode);
  const interestedModes = useUserStore((s) => s.interestedModes);
  return useMemo<Mode>(() => {
    if (override && override in MODE_BY_ID) return override;
    const first = interestedModes.find((m) => m in MODE_BY_ID);
    return (first as Mode | undefined) ?? "productividad";
  }, [override, interestedModes]);
}
