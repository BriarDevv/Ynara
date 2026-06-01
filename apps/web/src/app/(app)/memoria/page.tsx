import type { Metadata } from "next";
import { MemoryView } from "@/features/memory/components/MemoryView";

export const metadata: Metadata = {
  title: "Memoria",
};

/**
 * Sub-vista **Memoria** (timeline). Conecta al backend REAL `GET /v1/memory`
 * (build-plan Fase C1): lista cronológica, filtros por capa, estados
 * loading/empty/error. La página queda como server component (para exportar
 * `metadata`) y delega la interactividad al client `MemoryView`.
 */
export default function MemoriaPage() {
  return <MemoryView />;
}
