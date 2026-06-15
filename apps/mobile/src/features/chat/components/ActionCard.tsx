import type { Action } from "@ynara/shared-schemas";
import { Text, View } from "react-native";

/**
 * Card de una acción ejecutada por el agente (modos Qwen) — `Action` del
 * contrato (`name` + `arguments` + `result`). Solo productividad/memoria
 * producen acciones; Gemma no (ver `cannedActions`/ADR-002).
 *
 * Sin emojis (regla del repo): el acento es el **diamante violeta** de marca
 * para memoria (símbolo de memoria del onboarding) y un dot azul para
 * calendar/reminder. `result.status === "not_wired"` = tool stub (todavía sin
 * cablear en el backend) → se marca como acción de ejemplo.
 */
function describe(action: Action): { label: string; detail?: string; memory: boolean } {
  const args = action.arguments;
  const str = (v: unknown) => (typeof v === "string" ? v : undefined);
  if (action.name.startsWith("calendar")) {
    return { label: "Evento agendado", detail: str(args.title), memory: false };
  }
  if (action.name.startsWith("reminder")) {
    return { label: "Recordatorio", detail: str(args.title) ?? str(args.content), memory: false };
  }
  if (action.name.startsWith("memory")) {
    return { label: "Memoria guardada", detail: str(args.content), memory: true };
  }
  return { label: action.name, memory: false };
}

export function ActionCard({ action }: { action: Action }) {
  const { label, detail, memory } = describe(action);
  const notWired = action.result.status === "not_wired";

  return (
    <View className="flex-row items-start gap-3 rounded-md border border-border bg-bg-soft px-3 py-2.5">
      {memory ? (
        <View className="mt-1 h-2.5 w-2.5 rotate-45 rounded-[2px] bg-violeta" />
      ) : (
        <View className="mt-1 h-2.5 w-2.5 rounded-pill bg-azul" />
      )}
      <View className="flex-1 gap-0.5">
        <Text className="text-body-sm font-semibold text-ink">{label}</Text>
        {detail ? <Text className="text-body-sm text-ink-soft">{detail}</Text> : null}
        {notWired ? (
          <Text className="text-caption text-ink-muted">Acción de ejemplo (sin conectar)</Text>
        ) : null}
      </View>
    </View>
  );
}
