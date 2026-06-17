import { AvisosView } from "@/features/today/components/AvisosView";

export const metadata = { title: "Avisos" };

/**
 * Página **Avisos** — anticipaciones proactivas de Ynara.
 * Server component: renderiza el client component `AvisosView`.
 */
export default function AvisosPage() {
  return <AvisosView />;
}
