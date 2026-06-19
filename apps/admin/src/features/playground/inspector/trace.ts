import type { PlaygroundConfig } from "../components/PlaygroundControls";
import type { PlaygroundAgentOutT, PlaygroundOutT, ToolCallOutT, TraceStepT } from "../schemas";

/**
 * Modelo de vista del inspector (Fase A del trace, blueprint §4).
 *
 * Es el tipo PUENTE entre el contrato de wire (`PlaygroundOut`) y el render del
 * inspector: desacopla el componente del shape exacto del backend para que la
 * UI dependa de una forma estable y la Fase B (tool-loop) pueda enchufar
 * `tools` sin tocar el render del timeline ni del thinking.
 */

/** Estado visual de un nodo del timeline (sin verde/ámbar: no hay tokens). */
export type InspectorStepStatus = "ok" | "error" | "pending";

/** Un nodo del timeline ya resuelto a estado visual. */
export type InspectorStep = {
  /** Id del nodo (`"request" | "thinking" | "completion"`). */
  name: string;
  /** Texto humano del paso (viene armado del server, regla #4). */
  detail: string;
  /** Duración del paso en ms; solo `completion` la trae hoy. */
  durationMs?: number;
  /** Estado visual: en curso, ok o error. */
  status: InspectorStepStatus;
};

/**
 * Una tool-call observada del loop (Fase B, blueprint §4). Opcional en Fase A:
 * el inspector no lo pinta todavía, pero el tipo ya existe para no romper el
 * contrato del modelo de vista cuando llegue el modo agente.
 */
export type ToolCallTrace = {
  id: string;
  name: string;
  arguments: string;
  result: string;
  isError: boolean;
};

/** Lo que consume `PlaygroundInspector`: timeline + thinking (+ tools en F-B). */
export type InspectorTrace = {
  steps: InspectorStep[];
  /** El `<think>…</think>` separado, si el modelo lo expuso. */
  thinkingText?: string;
  /** Si el thinking efectivo estuvo encendido en este turno. */
  thinkingUsed: boolean;
  /** Tool-calls observadas (Fase B); ausente en el probe crudo de Fase A. */
  tools?: ToolCallTrace[];
};

/** Opciones de derivación: `isPending` marca el step en curso del timeline. */
type BuildTraceOptions = {
  isPending: boolean;
};

/**
 * Marca el último step del timeline como `pending` mientras la mutation está en
 * vuelo (el server todavía no devolvió el `trace`, así que sintetizamos un único
 * nodo "en curso"); con resultado, mapea cada `TraceStep` a su estado visual.
 */
function stepStatus(step: TraceStepT, finishReason: string): InspectorStepStatus {
  // El step `completion` hereda el veredicto del turno: cualquier finish_reason
  // distinto de `stop`/`length` (los cierres sanos) se pinta como error.
  if (step.name === "completion") {
    return finishReason === "stop" || finishReason === "length" ? "ok" : "error";
  }
  return "ok";
}

/**
 * Función PURA que mapea la config + el resultado del turno al modelo de vista
 * del inspector (blueprint §4). Sin side-effects ni dependencias de React: el
 * timeline y el thinking salen 100% derivados de `PlaygroundOut`.
 *
 * - `result === null` + `isPending` → un único nodo "request" en curso (el
 *   server aún no devolvió el trace), con el thinking elegido en la config.
 * - `result === null` + `!isPending` → trace vacío (sin turno todavía).
 * - con resultado → los `trace` del server resueltos a estado visual + el
 *   `thinking` separado.
 *
 * `tools` queda para Fase B (modo agente); en Fase A nunca se completa.
 */
export function buildTrace(
  config: PlaygroundConfig,
  result: PlaygroundOutT | null,
  { isPending }: BuildTraceOptions,
): InspectorTrace {
  if (result === null) {
    if (!isPending) {
      return { steps: [], thinkingUsed: config.thinking === "on" };
    }
    // En vuelo sin trace todavía: un nodo "request" pulsante hasta que llegue.
    return {
      steps: [{ name: "request", detail: config.model, status: "pending" }],
      thinkingUsed: config.thinking === "on",
    };
  }

  const steps: InspectorStep[] = result.trace.map((step) => ({
    name: step.name,
    detail: step.detail,
    durationMs: step.duration_ms ?? undefined,
    status: stepStatus(step, result.finish_reason),
  }));

  return {
    steps,
    thinkingText: result.thinking ?? undefined,
    thinkingUsed: result.thinking_used,
  };
}

/**
 * Heurística de error para una tool-call observada (blueprint §4): el result se
 * pinta como error cuando la tool no está cableada (`unknown_tool`, p. ej.
 * `memory.*` inalcanzable por construcción) o cuando el stub devolvió un fallo.
 * Los stubs sanos responden `not_wired`, que NO es error (es lo esperado en el
 * loop observado). La comparación es case-insensitive y por substring para no
 * acoplarnos al wording exacto del backend.
 */
function toolResultIsError(result: string): boolean {
  const normalized = result.toLowerCase();
  return normalized.includes("unknown_tool") || normalized.includes("error");
}

/** Mapea una `ToolCallOut` del wire al modelo de vista del inspector. */
function toToolCallTrace(action: ToolCallOutT): ToolCallTrace {
  return {
    id: action.id,
    name: action.name,
    arguments: action.arguments,
    result: action.result,
    isError: toolResultIsError(action.result),
  };
}

/**
 * Función PURA que mapea el resultado de un turno en **modo agente**
 * (`PlaygroundAgentOut`) al modelo de vista del inspector (blueprint §4).
 *
 * En modo agente el render se centra en las tool-call cards (`tools`), derivadas
 * de `actions`. El timeline queda vacío (el loop no expone los `TraceStep` por
 * iteración, limitación conocida del ADR) salvo que el backend mande `trace`, y
 * el thinking se respeta si viene expuesto. Mantiene la misma forma estable
 * (`InspectorTrace`) que `buildTrace` para que el inspector no ramifique.
 *
 * - `result === null` + `isPending` → un único nodo "agent" en curso (el loop
 *   todavía corre), con el thinking elegido en la config.
 * - `result === null` + `!isPending` → trace vacío (sin turno todavía).
 * - con resultado → las `actions` resueltas a tool-call cards (+ `trace`/
 *   `thinking` si el backend los expone).
 */
export function buildAgentTrace(
  config: PlaygroundConfig,
  result: PlaygroundAgentOutT | null,
  { isPending }: BuildTraceOptions,
): InspectorTrace {
  if (result === null) {
    if (!isPending) {
      return { steps: [], thinkingUsed: config.thinking === "on" };
    }
    // El loop está corriendo: un nodo "agent" pulsante hasta que llegue la traza.
    return {
      steps: [{ name: "agent", detail: config.model, status: "pending" }],
      thinkingUsed: config.thinking === "on",
    };
  }

  const steps: InspectorStep[] = result.trace.map((step) => ({
    name: step.name,
    detail: step.detail,
    durationMs: step.duration_ms ?? undefined,
    status: stepStatus(step, result.finish_reason),
  }));

  return {
    steps,
    thinkingText: result.thinking ?? undefined,
    thinkingUsed: result.thinking != null,
    tools: result.actions.map(toToolCallTrace),
  };
}
