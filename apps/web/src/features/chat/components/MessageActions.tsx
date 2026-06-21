import type { Action } from "@ynara/shared-schemas";
import { Icon, type IconName } from "@ynara/ui";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";

/**
 * Chips de "loop cerrado" debajo de una respuesta del assistant: hacen visible
 * que Ynara ejecutó una tool (agendar, recordar) en los modos agente. Hasta
 * acá el dato viajaba en `message.actions` (store + mock) pero no se renderizaba
 * en ningún lado, así que el feedback del modo agente era invisible.
 *
 * El `result` hoy es un stub `{status:"not_wired"}` (las tools reales llegan con
 * el backend), así que mostramos la intención ("Agendado", "Guardado en tu
 * memoria"), no un resultado inventado.
 *
 * TODO(backend): cuando `result` traiga estado real, distinguir éxito de error
 * (hoy el chip afirma la acción aunque la tool haya fallado) y mostrar el dato
 * concreto ("Agendado: mañana 10:00") desde `arguments`/`result`.
 */
const ACTION_META: Record<string, { label: string; icon: IconName }> = {
  "calendar.create_event": { label: "Agendado", icon: "recordatorio" },
  "memory.write": { label: "Guardado en tu memoria", icon: "red" },
};

function metaFor(name: string): { label: string; icon: IconName } {
  return ACTION_META[name] ?? { label: "Acción ejecutada", icon: "idea" };
}

export function MessageActions({ actions, mode }: { actions: Action[]; mode: ModeId }) {
  if (actions.length === 0) return null;
  const tint = MODE_BY_ID[mode].tintVar;
  return (
    <ul aria-label="Acciones que hizo Ynara" className="mt-2.5 flex flex-wrap gap-2">
      {actions.map((action) => {
        const meta = metaFor(action.name);
        return (
          <li key={action.id}>
            <span
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-2.5 py-1 text-body-sm text-[var(--color-ink)]"
              style={{
                borderColor: `color-mix(in srgb, ${tint} 30%, transparent)`,
                backgroundColor: `color-mix(in srgb, ${tint} 10%, var(--color-bg))`,
              }}
            >
              <Icon name={meta.icon} size={14} aria-hidden />
              {meta.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
