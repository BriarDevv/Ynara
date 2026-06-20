/**
 * Split de `<think>…</think>` tolerante a streaming (UX en vivo del Playground).
 *
 * El server ya devuelve el `thinking` autoritativo en el evento `done` (vía
 * `split_thinking` del backend), pero durante el stream necesitamos separar el
 * razonamiento del texto de respuesta **mientras llega**, incluso con el bloque
 * `<think>` todavía ABIERTO (el cierre `</think>` aún no streameó). Esto permite
 * mostrar "qué piensa el modelo" en vivo y que la burbuja de respuesta solo
 * muestre la respuesta real (no el razonamiento crudo).
 *
 * Casos:
 *  - sin `<think>` → todo es texto, thinking `null`.
 *  - `<think>` abierto sin cerrar (streaming) → lo previo es texto; lo posterior
 *    al tag es thinking en curso.
 *  - `<think>…</think>` cerrado → thinking = el interior; texto = lo de antes + lo
 *    de después concatenado.
 *
 * Qwen vía Ollama emite el tag plano `<think>`; no intentamos cubrir atributos
 * (`<think foo="bar">`) acá: el split definitivo lo hace el backend en `done`.
 */
const OPEN = "<think>";
const CLOSE = "</think>";

export function splitThinkingLive(raw: string): { text: string; thinking: string | null } {
  const open = raw.indexOf(OPEN);
  if (open === -1) return { text: raw, thinking: null };

  const close = raw.indexOf(CLOSE, open + OPEN.length);
  const before = raw.slice(0, open);

  // Bloque todavía abierto (el cierre no llegó): el resto es thinking en curso.
  if (close === -1) {
    const thinking = raw.slice(open + OPEN.length);
    return { text: before.trimStart(), thinking: thinking.length > 0 ? thinking : null };
  }

  const thinking = raw.slice(open + OPEN.length, close);
  const after = raw.slice(close + CLOSE.length);
  return {
    text: (before + after).trim(),
    thinking: thinking.length > 0 ? thinking : null,
  };
}
