import type { Metadata } from "next";
import { PlaygroundScreen } from "@/features/playground/components/PlaygroundScreen";

export const metadata: Metadata = { title: "Playground" };

/**
 * Playground · ruta "/playground" (ADR-018/019, control plane F3).
 *
 * Server component fino: delega TODA la composición a `<PlaygroundScreen/>`
 * (client). El chat es la superficie protagonista —ocupa el alto disponible con
 * scroll interno por panel—, así que la página NO mete un header editorial que
 * le robe espacio: el contexto (modelo activo, sesión) vive en el `ChatHeader`.
 *
 * Probe del modelo en STREAMING: manda mensajes ad-hoc al modelo elegido y ve la
 * respuesta token-por-token + tok/s, con historial de sesiones (client-side),
 * salud del serving e inspector del turno. Aislado: no toca memoria, sesiones del
 * producto ni el serving global.
 */
export default function PlaygroundPage() {
  return <PlaygroundScreen />;
}
