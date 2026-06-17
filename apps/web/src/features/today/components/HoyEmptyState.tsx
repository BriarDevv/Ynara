"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { useActiveMode } from "@/hooks/useActiveMode";

/**
 * Estado vacío completo de Hoy (wireframe 07 / build-plan E5): cuando no hay
 * prioridades, en vez de un hint compacto se muestra una composición editorial
 * — el orbe de marca (teñido por el modo activo), un respiro de copy y el
 * siguiente paso natural: hablar con Ynara. Reemplaza el `EmptyStateCard` chico
 * de `PrioritiesSection`.
 */
export function HoyEmptyState() {
  const router = useRouter();
  const activeMode = useActiveMode();

  return (
    <section className="flex flex-col items-center gap-4 rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg)] px-6 py-12 text-center">
      <YnaraOrb size={72} modeId={activeMode} />
      <div className="flex flex-col gap-1">
        <h2 className="text-subtitle text-[var(--color-ink-deep)]">Tu día está despejado</h2>
        <p className="max-w-[44ch] text-body text-[var(--color-ink-soft)]">
          Nada urgente por ahora. Aprovechá el respiro, o arrancá algo con Ynara.
        </p>
      </div>
      <Button onClick={() => router.push("/chat")}>Hablar con Ynara</Button>
    </section>
  );
}
