import type { Metadata } from "next";
import { MemoryDetailRoute } from "@/features/memory/components/MemoryDetailRoute";

export const metadata: Metadata = {
  title: "Recuerdo",
};

// El detalle del backend necesita `{layer}/{ref}`, pero la ruta es de un solo
// segmento (`[id]` = ref); la capa viaja por query `?capa=`. La página extrae
// ambos y delega en el dispatcher cliente, que valida la capa y aplica los
// estados. Dynamic: el ref/capa salen del request, no se prerenderiza.
export const dynamic = "force-dynamic";

export default async function MemoriaDetallePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ capa?: string }>;
}) {
  const { id } = await params;
  const { capa } = await searchParams;
  return <MemoryDetailRoute memoryRef={id} rawLayer={capa} />;
}
