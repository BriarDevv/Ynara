import type { Metadata } from "next";
import { PlaygroundScreen } from "@/features/playground/components/PlaygroundScreen";

export const metadata: Metadata = { title: "Playground" };

/**
 * Playground · ruta "/playground" (ADR-018 F1, control plane F3).
 *
 * Server component: header editorial estático + `metadata`, delega la
 * composición de datos a `<PlaygroundScreen/>` (client, consume `useServing()` +
 * `usePlayground()`). NO lleva `range` —es runtime/config, foto única—.
 *
 * Probe del modelo CRUDO: manda un mensaje ad-hoc a un modelo elegido con params
 * per-request (incluido el preset "bajo rendimiento") **sin** mutar el serving
 * global, sin sesión/memoria/tools. El "bajo rendimiento" es por mensaje, no
 * global (frontera F1/F2 del ADR-018).
 */
export default function PlaygroundPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="anim-fade-in flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Playground</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Probá un modelo del serving con un mensaje ad-hoc y parámetros por turno (incluido el modo
          bajo rendimiento). Aislado: no toca memoria, sesiones ni el serving global.
        </p>
      </header>

      <PlaygroundScreen />
    </section>
  );
}
