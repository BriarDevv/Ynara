import { ModeDonut } from "@/components/charts/ModeDonut";
import { Card } from "@/components/ui/Card";
import type { AdminModesOutT } from "@/features/modes/schemas";

type Props = {
  /** `mix` del contrato de modos: una entrada por modo con sesiones y %. */
  mix: AdminModesOutT["mix"];
  /** Total de sesiones en el rango (centro del donut). */
  total: number;
  className?: string;
};

/**
 * F1.3 · Banda 1 — Mix de modos.
 *
 * Tarjeta editorial que envuelve `<ModeDonut/>`: cada slice usa el `fillVar`
 * oficial del modo (color plano, sin gradiente), el centro muestra el total con
 * count-up + `tabular-nums`, y la leyenda lateral lleva `ModeChip` + conteo + %.
 *
 * Server component: solo proyecta datos al chart (que sí es client por el
 * count-up/tooltip); acá no hay estado ni efectos.
 */
export function ModeMix({ mix, total, className }: Props) {
  // El donut quiere `{ mode, value }`; mapeamos `sessions → value`.
  const data = mix.map((m) => ({ mode: m.mode, value: m.sessions }));

  return (
    <Card className={className}>
      <header className="mb-6 flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Mix de sesiones</p>
        <h2 className="text-subtitle text-[var(--color-ink-deep)]">Cómo se reparten los modos</h2>
      </header>
      <ModeDonut data={data} total={total} />
    </Card>
  );
}
