import { create } from "zustand";

/**
 * Estado compartido de avisos (anticipaciones) **resueltos**, única fuente para
 * los tres consumidores que antes tenían estado propio y se desincronizaban:
 *  - `AnticipationsSection` (Hoy): descartar una card.
 *  - `AvisosView` (/avisos): resolver una card.
 *  - `SidebarNav` (AppNav): el badge de pendientes.
 *
 * Resolver en cualquiera de los tres se refleja en los otros (descartar en Hoy
 * lo deja resuelto en /avisos, y el badge baja). En memoria, no se persiste:
 * espeja el comportamiento de sesión del mock actual (sin backend), pero
 * compartido. Cuando exista el endpoint, el set de pendientes saldrá del server.
 */
type AvisosState = {
  resolvedIds: Set<string>;
  /** Marca un aviso como resuelto (idempotente). */
  resolve: (id: string) => void;
  reset: () => void;
};

export const useAvisosStore = create<AvisosState>((set) => ({
  resolvedIds: new Set(),
  resolve: (id) => set((s) => ({ resolvedIds: new Set(s.resolvedIds).add(id) })),
  reset: () => set({ resolvedIds: new Set() }),
}));
