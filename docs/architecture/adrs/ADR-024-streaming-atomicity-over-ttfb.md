# ADR-024: Streaming SSE cosmético — atomicidad transaccional del turno por encima del TTFB real (SCAL-01)

## Estado
Aceptado

## Fecha
2026-06-25

## Contexto

`POST /v1/chat/stream` ([`apps/backend/app/api/v1/chat.py`](../../../apps/backend/app/api/v1/chat.py))
expone el turno de chat como un stream SSE con eventos con nombre (`token` /
`done` / `error`) que consume el parser de
[`packages/shared-schemas/src/sse.ts`](../../../packages/shared-schemas/src/sse.ts).
El front lo usa para pintar la respuesta "token por token" en el chat.

La pregunta arquitectónica que amerita ADR es **cuándo corre el trabajo del
turno respecto del stream**. Hay dos formas estructuralmente distintas:

1. **SSE real del LLM (token-true).** Abrir el `StreamingResponse` primero y
   emitir cada delta a medida que el modelo lo produce (el LLM ya streamea). El
   TTFB (time-to-first-byte) es el real: el primer token llega ni bien el modelo
   lo emite.
2. **SSE cosmético (post-turno).** Correr el turno **completo** primero
   (router LLM + persistencia de turnos + commit + enqueue post-commit, todo en
   `ChatService.run_turn`) y, recién con la respuesta final ya commiteada,
   trocear `resp.text` en chunks de ventana fija y emitirlos como eventos
   `token`. El "streaming" que ve el cliente es una animación sobre un texto que
   ya existe entero.

El backend hoy implementa la **opción 2**. El detalle verificado contra el
código:

- El generator trocea `text` en ventanas de `_TOKEN_CHUNK_SIZE = 6` code-points
  (`chat.py:79`, `chat.py:305-306`); `''.join(deltas)` reconstruye `resp.text`
  byte-a-byte (invariante dura del wire). Son chunks **cosméticos**, no tokens
  del modelo.
- TODO el trabajo transaccional ocurre ANTES de construir el
  `StreamingResponse` (`chat.py:273-279`): `resolve_chat_session` →
  `ChatService.run_turn` (`route()` → persistir turnos → `commit` → enqueue
  post-commit). El generator solo serializa primitivos ya snapshoteados
  (`chat.py:287-298`).

Eso no es un accidente: es el **mismo fix de orden transaccional** que el
`/chat` no-stream documenta como decisión M9 (la "decisión #1" del docstring del
módulo, criticada adversarialmente y marcada "NO re-litigar"). Congelarlo como
ADR cierra el tradeoff explícito antes de que un refactor futuro lo "modernice"
hacia SSE nativo y rompa la garantía sin querer (ya hay un comentario defensivo
en `chat_stream`, decisión #3, advirtiendo justo eso).

## Decisión

**En el MVP, `/chat/stream` corre el turno completo y commiteado ANTES de abrir
el stream; el streaming es cosmético (chunks de ventana fija sobre el texto
final). Se prioriza la atomicidad transaccional del turno por encima del TTFB
real.**

### Por qué atomicidad > TTFB

El turno de chat es transaccional: persiste los turnos USER + MODEL, commitea y
recién entonces enqueuea el trabajo post-commit (consolidación episódica). La
opción cosmética garantiza que:

- **Un fallo del turno propaga ANTES del `StreamingResponse`.** Si algo falla
  en `run_turn` —incluido el `commit`— la excepción sube antes de devolver la
  response, `get_db()` hace rollback y el cliente recibe un **500 limpio con 0
  bytes SSE**: el stream nunca arrancó (`chat.py:239-244`, decisión #1). No
  existe el estado intermedio "ya emití 40 tokens y ahora la transacción
  revienta".
- **Los errores de validación / auth / sesión (422 / 401 / 404 / 409) saltan
  como HTTP normales**, no como eventos `event: error` dentro de un stream ya
  abierto. El cliente los ve como status codes, que es lo que el contrato de
  `sse.ts` espera.
- **Sin lazy-load post-commit.** El generator cierra SOLO sobre `str` /
  `list[dict]` ya serializados (`chat.py:287-298`, decisión #2); nunca sobre
  `chat_session` ni atributos ORM, que tras el commit dispararían I/O sobre una
  sesión ya cerrada.

Con SSE real (opción 1) la respuesta HTTP se compromete (status 200 + headers)
**antes** de saber si el turno commitea. Un fallo a mitad de stream deja al
cliente con una respuesta parcial y a la DB potencialmente sin el turno MODEL
persistido — o peor, con el commit hecho pero el stream cortado. Recuperar la
atomicidad ahí exige buffering, sentinelas de fin-de-stream y reconciliación
cliente-side: complejidad que el MVP no necesita.

### Costo asumido

El **TTFB es el del turno completo**, no el del primer token del modelo. El
usuario espera a que el LLM termine de generar (más el tool-loop, más el commit)
antes de ver el primer chunk; la animación token-por-token es percepción, no
latencia real ganada. Para el MVP —corpus chico, 1-2 workers (ADR-020),
respuestas cortas— ese TTFB es aceptable y el determinismo transaccional vale
más que la sensación de inmediatez.

## Consecuencias positivas

- **Atomicidad del turno garantizada**: o el turno commitea entero y el cliente
  recibe `token*` + `done`, o falla antes de abrir el stream y recibe un 500 con
  0 bytes. No hay respuesta parcial con transacción a medias.
- **Mapeo de errores HTTP limpio**: 422/401/404/409/429/500 saltan como status
  codes reales, no enmascarados dentro de un stream SSE ya iniciado.
- **Generator trivialmente seguro**: cierra sobre primitivos pre-serializados;
  cero riesgo de lazy-load ORM post-commit, cero acoplamiento al lifecycle de la
  sesión DB.
- **Contrato de wire estable**: `''.join(deltas) == resp.text` es una invariante
  dura y testeable; el mismo `run_turn` alimenta `/chat` y `/chat/stream`, así
  que ambos endpoints no pueden divergir en comportamiento de dominio.

## Consecuencias negativas

- **El TTFB no es real**: el usuario espera el turno completo antes del primer
  chunk. En respuestas largas o con tool-loop lento, la animación arranca tarde
  y la ventaja perceptual del streaming se diluye.
- **No se aprovecha el streaming nativo del LLM**: el modelo ya emite tokens
  incrementalmente y acá se descartan en favor de re-trocear el texto final.
- **`_TOKEN_CHUNK_SIZE` es un parámetro cosmético** sin relación con tokens
  reales del modelo; es UX, no semántica.

## Mitigaciones

- El troceo cosmético mantiene la **misma UX visible** que un stream real para
  respuestas cortas del MVP: el usuario percibe "está escribiendo" igual.
- El `try/except` del generator (`chat.py:309-313`) es una red de seguridad que
  emite un `event: error` neutro (sin PII, regla #4) si algo improbable falla
  durante la serialización, aunque en la práctica todo el payload está
  pre-serializado antes de entrar al generator.

## Trigger de re-evaluación (cuándo conviene SSE real del LLM)

Migrar a streaming token-true (opción 1) se justifica cuando se cumpla
**cualquiera** de estas condiciones, medidas en producción, no temidas:

1. **TTFB percibido inaceptable**: respuestas suficientemente largas (o
   tool-loops suficientemente lentos) como para que el delay hasta el primer
   chunk degrade la UX de forma medida (no anecdótica).
2. **Necesidad de cancelación temprana**: el usuario quiere poder cortar la
   generación a mitad de respuesta (hoy imposible: el turno ya está commiteado
   cuando arranca el stream).
3. **Respuestas largas con costo de espera real**: cuando el valor de ver los
   primeros tokens mientras el resto se genera supere el costo de perder la
   atomicidad simple.

El plan, llegado ese punto, es **no** descartar la garantía de atomicidad sino
recuperarla bajo streaming real: persistir el turno USER + abrir el stream del
LLM bufferizando el texto MODEL, y commitear el turno MODEL **al cierre** del
stream (con un sentinel de fin-de-stream explícito y reconciliación cliente-side
ante corte). Es estrictamente más complejo que lo actual — por eso se difiere
hasta que la medición lo pida.

## Alternativas descartadas

- **SSE real del LLM (token-true) en el MVP.** Es la opción "obvia" de
  streaming, pero compromete el status HTTP 200 antes de saber si el turno
  commitea: un fallo a mitad de stream deja respuesta parcial + transacción a
  medias. Recuperar atomicidad ahí exige buffering + sentinelas + reconciliación
  que el MVP no necesita. Diferida al trigger de arriba.
- **Devolver `ChatHttpResponse` JSON y que el front "anime" el texto.** Sería el
  mismo tradeoff (atomicidad > TTFB) pero perdiendo el contrato SSE que el front
  ya consume y la simetría con un futuro stream real. El SSE cosmético da la UX
  de streaming sin cambiar de transporte cuando se migre.
- **Endpoint async-gen nativo de FastAPI / `EventSourceResponse`.** Descartado
  explícitamente en `chat.py` (decisión #3): a partir de FastAPI 0.136 el
  soporte SSE nativo cambiaría el wire (formato de eventos) y el lifecycle
  (cuándo corre el generator vs cuándo se cierra la sesión DB). Devolver el
  `StreamingResponse` a mano fija el contrato exacto que `sse.ts` espera.

## Links

- [`apps/backend/app/api/v1/chat.py`](../../../apps/backend/app/api/v1/chat.py) —
  `chat_stream` (orden transaccional + snapshot de primitivos + generator).
- [`packages/shared-schemas/src/sse.ts`](../../../packages/shared-schemas/src/sse.ts) —
  parser del wire SSE (`token` / `done` / `error`).
- [`ADR-020`](./ADR-020-circuit-breaker-cota-workers.md) — cota de despliegue 1-2
  workers (contexto de la carga del MVP).
- [`ADR-022`](./ADR-022-tools-sincronos-en-chat.md) — tools síncronas en el chat
  de producción (el turno que se streamea).
