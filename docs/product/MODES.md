# MODES.md — Los 5 modos de Ynara

Ynara tiene 5 modos. Cada uno cambia el modelo, el tono, las capas de
memoria activas y las tools habilitadas. La configuración canónica
vive en [`ynara.config.json`](../../ynara.config.json).

## Tabla resumen

| Modo | Modelo | Capas de memoria | Tools | Tono |
|------|--------|------------------|-------|------|
| Productividad | Qwen 3.5-9B | semantic, episodic | calendar, reminder, memory | neutro-eficaz |
| Estudio | Gemma 4 12B | episodic, procedural | — | encouragement |
| Bienestar | Gemma 4 12B | procedural, semantic | — | casual-empatico |
| Vida | Gemma 4 12B | procedural | — | casual-rioplatense |
| Memoria | Qwen 3.5-9B | episodic, semantic, procedural | memory | neutro-eficaz |

## Productividad

> Para cerrar loops. Agendar, recordar, ejecutar.

- Modelo: Qwen 3.5-9B (agente).
- Lee y escribe memoria.
- Tools: `calendar.*`, `reminder.*`, `memory.*`.
- Tono: directo, eficaz, sin chamuyo. Confirma acciones tomadas.

Ejemplos:
- "Recordame estudiar Cálculo II hoy a las 7 PM."
- "¿Qué tengo agendado mañana?"
- "Anotá que el final de Sistemas es el 4 de junio."

## Estudio

> Para entender, no para hacer la tarea.

- Modelo: Gemma 4 12B (conversacional).
- Lee memoria episódica + procedural. No escribe.
- Sin tools — sesión cerrada de tutoría.
- Tono: aliento + claridad. Explicaciones desde lo que el usuario ya
  sabe.

Ejemplos:
- "No entiendo bien teorema del valor medio."
- "Tomame un quiz de 5 preguntas sobre lo último."

## Bienestar

> Para descomprimir. Acompañar sin terapizar.

- Modelo: Gemma 4 12B.
- Lee memoria procedural + semántica. No escribe.
- Sin tools.
- Tono: cálido sin pegote. **Prohibido** consejos clínicos, prohibido
  diagnosticar, prohibido moralizar.

Reglas duras:
- Si el usuario menciona ideación suicida, autolesión o crisis aguda,
  Ynara entrega **información de líneas de ayuda locales** y se
  retira. Nunca actúa como reemplazo de profesional.
- TODO: cerrar protocolo exacto con el equipo + revisión legal.

## Vida

> Charla cotidiana, recomendaciones livianas.

- Modelo: Gemma 4 12B.
- Lee memoria procedural. No escribe.
- Sin tools: Gemma es conversacional y solo lee memoria; las acciones
  (calendar incluido) las maneja Qwen en Productividad (ADR-002).
- Tono: casual rioplatense. Voseo, modismos, sin afectación.

Ejemplos:
- "Qué hago para comer hoy."
- "Recomendame una serie corta."

## Memoria

> Para recordar lo que se dijo. Recall explícito.

- Modelo: Qwen 3.5-9B (agente).
- Lee y escribe memoria (las 3 capas).
- Tool: `memory.*`.
- Tono: neutro-eficaz, cita textual cuando aplica.

Ejemplos:
- "¿Qué te dije la semana pasada sobre el trabajo?"
- "Borrame todo lo que tengas sobre [tema]."

## Cambio de modo

- El usuario puede cambiar de modo explícitamente desde la UI.
- El agente Qwen puede sugerir un cambio de modo si detecta intent
  fuera del modo actual (ej: en Bienestar el usuario pide agendar
  algo).
- El cambio se logea: el modo es contexto y queda en memoria
  episódica de la sesión.

## Agregar un modo nuevo

Cualquier modo nuevo requiere:
1. ADR aprobado.
2. Entrada en `ynara.config.json[modes]`.
3. Sección en este archivo.
4. Tests de tono/comportamiento.

Ver `skills/add-new-mode/SKILL.md` para el procedimiento.
