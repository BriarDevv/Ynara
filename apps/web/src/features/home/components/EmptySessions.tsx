import { EmptyStateCard } from "@/components/ui/EmptyStateCard";

/**
 * Estado vacío de conversaciones (plan §5.5). Cuando haya sesiones reales
 * se reemplaza por una SessionsList.
 */
export function EmptySessions() {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-caption text-[var(--color-ink-muted)]">Tus conversaciones</h2>
      <EmptyStateCard
        field
        title="Acá vive lo que vamos hablando"
        hint="Empezá una conversación abajo y la vas a ver tejerse en tu red."
      />
    </section>
  );
}
