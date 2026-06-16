import { useLocalSearchParams } from "expo-router";
import { MemoryDetailScreen } from "@/features/memory/MemoryDetailScreen";

// Ruta del detalle de un recuerdo: /memoria/<ref>?capa=<capa>. Vive en el stack
// raíz (no en el tab) → abre full-screen por encima del tab bar. El `ref` es el
// id (semantic/episodic) o la key (procedural); la capa llega por query.
export default function MemoryDetailRoute() {
  const { ref, capa } = useLocalSearchParams<{ ref: string; capa?: string }>();
  if (!ref) return null;
  return <MemoryDetailScreen memoryRef={ref} rawLayer={capa} />;
}
