import type { Metadata } from "next";
import type { ReactNode } from "react";

// La page de /hoy es client component (hooks de store), así que el título lo
// aporta este layout server — paridad con las otras tabs (Chat/Agenda/Tú),
// que exportan `metadata` directo. Compone con el template del root layout
// (`%s — Ynara`).
export const metadata: Metadata = {
  title: "Hoy",
};

export default function HoyLayout({ children }: { children: ReactNode }) {
  return children;
}
