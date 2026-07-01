"use client";

import { createContext, useContext } from "react";

export interface DeckCtx {
  /** Índice 0-based de la lámina activa. */
  active: number;
  /** Total de láminas. */
  total: number;
  /** Dirección del último cambio (1 = avanzar, -1 = retroceder) — para el sentido del crossfade. */
  dir: number;
  go: (i: number) => void;
  next: () => void;
  prev: () => void;
}

export const DeckContext = createContext<DeckCtx | null>(null);

export function useDeck(): DeckCtx {
  const ctx = useContext(DeckContext);
  if (!ctx) throw new Error("useDeck debe usarse dentro de <Deck>");
  return ctx;
}

/** `true` cuando la lámina `index` es la activa. */
export function useSlideActive(index: number): boolean {
  return useDeck().active === index;
}
