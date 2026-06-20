import type { Metadata } from "next";
import { SharingView } from "@/features/sharing/components/SharingView";

export const metadata: Metadata = { title: "Conexión / Compartir" };

/**
 * Conexión / Compartir · ruta "/compartir".
 *
 * Server component: header editorial estático + `metadata`, delega la composición
 * de datos a `<SharingView/>` (client, consume `useConnectivity()`). Estado del
 * tailnet de Tailscale + las URLs para que otra máquina consuma el serving: la API
 * OpenAI-compatible de Ollama y el chat de Open WebUI.
 */
export default function CompartirPage() {
  return (
    <section className="flex flex-col gap-8">
      <header className="anim-fade-in flex flex-col gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">Soberanía</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Conexión / Compartir</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Estado de tu tailnet de Tailscale y las URLs para que otra máquina consuma el serving: la
          API OpenAI-compatible de Ollama y el chat de Open WebUI.
        </p>
      </header>

      <SharingView />
    </section>
  );
}
