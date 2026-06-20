import { createA11yStore } from "@ynara/core/stores";
import { memoryStorage } from "@/lib/memoryStorage";

// Instancia mobile del store de a11y (ADR-016). Por ahora sobre memoria;
// persistir las prefs entre reinicios (AsyncStorage/MMKV) y aplicarlas
// app-wide (escala de fuente) son follow-ups. En el onboarding alcanza con
// capturarlas y trasladarlas al user store al cerrar.
export const useA11yStore = createA11yStore(memoryStorage);
