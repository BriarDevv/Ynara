import type { Action } from "@ynara/shared-schemas";
import { Icon, type IconName } from "@ynara/ui";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";

/**
 * Chips de "loop cerrado" debajo de una respuesta del assistant: hacen visible
 * que Ynara ejecutó una tool (agendar, recordar) en los modos agente. El dato
 * viaja en `message.actions` (store + backend/mock).
 *
 * El `result` de cada acción (dict del backend) puede traer `{ error }` si la tool
 * FALLÓ: en ese caso el chip muestra el fallo ("No se pudo agendar") con estilo de
 * error en vez de afirmar un éxito inventado. El stub actual (`{ status:
 * "not_wired" }`) y el éxito caen al chip de intención.
 *
 * TODO(backend): cuando `result` traiga el dato concreto, mostrarlo ("Agendado:
 * mañana 10:00") desde `arguments`/`result`.
 */
const ACTION_META: Record<string, { label: string; failLabel: string; icon: IconName }> = {
  "calendar.create_event": {
    label: "Agendado",
    failLabel: "No se pudo agendar",
    icon: "recordatorio",
  },
  "memory.write": {
    label: "Guardado en tu memoria",
    failLabel: "No se pudo guardar",
    icon: "red",
  },
};

function metaFor(name: string): { label: string; failLabel: string; icon: IconName } {
  return (
    ACTION_META[name] ?? {
      label: "Acción ejecutada",
      failLabel: "No se pudo completar la acción",
      icon: "idea",
    }
  );
}

/**
 * ¿La tool falló? El `result` (dict del backend) reporta el fallo con `error`
 * (`{ code, message }`). El stub (`{ status: "not_wired" }`) y el éxito no lo
 * traen, así que solo marcamos fallo cuando `error` está presente. Hoy ningún chip
 * cae acá (todo es `not_wired`); cuando el backend ejecute tools reales, una falla
 * deja de mostrarse como éxito.
 */
function actionFailed(result: Action["result"]): boolean {
  return "error" in result && result.error != null;
}

export function MessageActions({ actions, mode }: { actions: Action[]; mode: ModeId }) {
  if (actions.length === 0) return null;
  const tint = MODE_BY_ID[mode].tintVar;
  return (
    <ul aria-label="Acciones que hizo Ynara" className="mt-2.5 flex flex-wrap gap-2">
      {actions.map((action) => {
        const meta = metaFor(action.name);
        const failed = actionFailed(action.result);
        return (
          <li key={action.id}>
            <span
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-2.5 py-1 text-body-sm text-[var(--color-ink)]"
              style={
                failed
                  ? {
                      color: "var(--color-error)",
                      borderColor: "color-mix(in srgb, var(--color-error) 35%, transparent)",
                      backgroundColor: "var(--color-error-soft)",
                    }
                  : {
                      borderColor: `color-mix(in srgb, ${tint} 30%, transparent)`,
                      backgroundColor: `color-mix(in srgb, ${tint} 10%, var(--color-bg))`,
                    }
              }
            >
              <Icon name={meta.icon} size={14} aria-hidden />
              {failed ? meta.failLabel : meta.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
