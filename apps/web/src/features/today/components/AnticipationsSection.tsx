"use client";

import { useMemo, useState } from "react";
import { buildAnticipations } from "../anticipations";
import { AnticipationCard } from "./AnticipationCard";

/**
 * Sección **Anticipación** de la vista Hoy: renderiza las anticipaciones
 * canned de Ynara entre el header y las Prioridades. Cuando todas se
 * descartan (o no hay ninguna), la sección desaparece sin dejar hueco.
 *
 * `aria-live="polite"` anuncia el cambio al stack de accesibilidad cuando
 * las cards aparecen o desaparecen dinámicamente.
 */
export function AnticipationsSection() {
  const initial = useMemo(() => buildAnticipations(), []);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = initial.filter((a) => !dismissed.has(a.id));

  if (visible.length === 0) return null;

  return (
    <section aria-live="polite" className="flex flex-col gap-3">
      {visible.map((anticipation) => (
        <AnticipationCard
          key={anticipation.id}
          anticipation={anticipation}
          onDismiss={() => setDismissed((prev) => new Set([...prev, anticipation.id]))}
        />
      ))}
    </section>
  );
}
