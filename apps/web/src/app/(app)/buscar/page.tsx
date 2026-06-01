import type { Metadata } from "next";
import { BuscarView } from "@/features/memory/components/BuscarView";

export const metadata: Metadata = {
  title: "Buscar",
};

// Acepta `?q=` para entrar con una búsqueda ya cargada (link compartible). La
// página extrae la query inicial y delega en el client `BuscarView`, que maneja
// el input, el debounce y los estados. Dynamic: la query sale del request.
export const dynamic = "force-dynamic";

export default async function BuscarPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  return <BuscarView initialQuery={q ?? ""} />;
}
