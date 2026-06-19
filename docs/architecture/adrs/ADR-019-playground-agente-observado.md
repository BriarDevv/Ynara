# ADR-019: Playground agente observado (tool-loop sin efectos) — refina ADR-018

## Estado

Aceptado

<!-- Aprobado por @BriarDevv (CODEOWNER) el 2026-06-19 ("te doy permiso para todo
     100% de confianza"). Refina ADR-018: incorpora un modo agente OBSERVADO al
     playground como superficie separada. -->

## Fecha

2026-06-19

## Contexto

[ADR-018](./ADR-018-admin-playground-modelos.md) creó el playground admin (fase
1) y fijó por escrito su frontera (D1): el endpoint `POST /v1/admin/playground`
llama `complete()` **directo**, **sin `run_tool_loop()`** y **sin `DbSession`** —
un probe del modelo crudo, aislado.

El operador además quiere **ver al agente trabajar**: cómo razona, qué tools
decide llamar y con qué argumentos, paso a paso ("cómo se activan los endpoints
y qué hacen"). Eso requiere correr el tool-loop real del agente (qwen), lo que
**invierte** la frontera escrita de ADR-018. Por eso este refinamiento.

Hechos verificados del código que hacen esto seguro:

- `run_tool_loop(...)` ya devuelve `actions` — la lista de `{id, name,
  arguments, result}` por iteración — sin instrumentar nada.
- `default_registry()` contiene **solo** las tools de `calendar` y `reminder`,
  todas **stubs `not_wired`** (cero efecto). **No** incluye `memory`.
- Las dos únicas tools con escritura real (`memory.update`, `memory.delete`)
  viven en `memory_registry()`, que es **opt-in**.
- `MAX_TOOL_ITERATIONS = 5` acota el loop.

## Decisión

### D1 — Endpoint separado, observado, a cero efecto

Se agrega `POST /v1/admin/playground/agent` (gateado `CurrentAdmin`), **separado**
de `/playground` para no contaminar la semántica "probe crudo" de ADR-018 (que
sigue vigente). Corre el tool-loop real del modelo elegido pero con registries
que hacen **imposible** tocar datos reales:

```
registries = (default_registry(), None)   # None = SIN memory_registry
```

- Las 4 tools del default (`calendar.create_event`/`list_events`,
  `reminder.set`/`list`) son **stubs `not_wired`**: el modelo las llama, se
  observan `name` + `arguments` + `result` ("not_wired"), cero efecto.
- Cualquier `memory.*` que el modelo intente cae en `unknown_tool` (observable,
  sin efecto) porque el `memory_registry` **ni se construye** en este path.
- `memory.update`/`memory.delete` son **inalcanzables por construcción**, no por
  convención.

La respuesta es `PlaygroundAgentOut` con `text`, `actions` (tool calls
observadas), `finish_reason`. Mismas validaciones que `/playground` (modelo
servido → 422, serving fake → 409, mapeo `LlmError`→status sin ecoar payload).

### D2 — Invariante de no-efecto (no negociable)

**Prohibido** inyectar `memory_registry()` real (o cualquier registry con
side-effects) en este endpoint. Un test debe **fallar** si alguien lo hace. Esta
es la barrera real (por construcción), más fuerte que el ADR mismo. Una variante
futura para `memory.search` (read-only) solo sería admisible con un store sobre
una transacción revertida; queda fuera de alcance.

### D3 — Frontera

- `/v1/admin/playground` (ADR-018): probe crudo, `complete()` directo. **Sin
  cambios.**
- `/v1/admin/playground/agent` (este ADR): tool-loop observado, stubs, cero
  efecto. Superficie nueva.
- El control **global** runtime del serving (cambiar lo que usa el producto)
  sigue siendo fase 2 diferida (ADR-018 D2). Esto NO es eso: es observar, no
  mutar el producto.

## Consecuencias positivas

- El operador ve al agente real (qwen) decidir y llamar tools, paso a paso — el
  corazón de "checkear que todo anda".
- Cero efecto por construcción: sin `memory_registry`, las tools con write son
  inalcanzables; blindado con un test.
- Aditivo a nivel de código: endpoint nuevo, cero cambios en `tool_loop.py`,
  `app/memory/` o `alembic/versions/` → **no** dispara regla #1 ni #3.

## Consecuencias negativas

- `memory.search` (read-only útil) no se muestra en v1 (necesitaría `DbSession`
  + store, que arrastra `app/memory/` → regla #3). Diferido.
- `run_tool_loop` sobrescribe los `CompletionResult` intermedios: las tool-call
  cards muestran `args`/`result`/`iter n/5` pero **no** tokens/latencia por
  iteración. Limitación conocida; instrumentar el loop sería un cambio mayor.
- Útil solo contra serving real (`LLM_BACKEND=vllm`); contra fake responde 409
  (en dev el inspector se prueba con MSW).

## Alternativas descartadas

- **Reusar `/playground` con un flag `agent_mode`**: contamina la semántica
  "probe crudo" y mezcla dos shapes de respuesta. Descartada a favor de un
  endpoint separado.
- **Solo `FakeLlmClient` con tool_calls guionadas** (sin modelo real): evitaría
  el ADR, pero se pierde lo valioso (ver al qwen real decidir). Descartada como
  modo principal (sí se usa en los tests).
- **Inyectar `memory_registry()` para mostrar memoria**: rompe el invariante de
  no-efecto y arrastra regla #3. Descartada.

## Relación con otros ADRs

- **Refina** [ADR-018](./ADR-018-admin-playground-modelos.md) (mueve su frontera
  D1 para una superficie nueva y separada; el `/playground` original sigue igual).
- Hereda el gate de auth admin y las invariantes de privacidad (regla #4) de
  ADR-017/ADR-018.
