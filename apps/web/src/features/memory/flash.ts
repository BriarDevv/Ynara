/**
 * Mensaje efímero (sessionStorage) para mostrar un toast tras navegar entre
 * vistas de memoria. El detalle se desmonta al borrar (navega al timeline), así
 * que el acuse de "Recuerdo borrado." se siembra acá y lo levanta `MemoryView`
 * al aterrizar. La edición no navega, así que muestra su toast in-place.
 */
export const MEMORY_FLASH_KEY = "ynara.memory.flash";

/** Siembra un mensaje flash para la próxima vista de memoria (no-op en SSR). */
export function setMemoryFlash(message: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(MEMORY_FLASH_KEY, message);
}

/** Consume (lee y borra) el mensaje flash pendiente, si hay (no-op en SSR). */
export function takeMemoryFlash(): string | null {
  if (typeof window === "undefined") return null;
  const message = window.sessionStorage.getItem(MEMORY_FLASH_KEY);
  if (message) window.sessionStorage.removeItem(MEMORY_FLASH_KEY);
  return message;
}
