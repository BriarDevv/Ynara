# ADR-018: Playground de modelos en el panel admin (control plane, fase 1)

## Estado

Aceptado

<!-- Aprobado por @BriarDevv (CODEOWNER) el 2026-06-19 ("te doy permiso para todo
     100% de confianza"), habilitando la implementación de la fase 1. Refina
     ADR-013/ADR-014 y materializa la fase 1 del control plane previsto en
     ADR-017 D7. -->

## Fecha

2026-06-19

## Contexto

[ADR-017](./ADR-017-admin-app-observabilidad-control-plane.md) D7 registró el
**control plane** del serving como objetivo del panel interno (`apps/admin`):
poder operar las IAs desde el panel — ver qué se sirve, elegir modelos, un
"modo bajo rendimiento", y un chat para probar — y lo dejó explícitamente detrás
de un ADR de refinamiento bajo el gate de regla #1 (toca serving). Este ADR es
ese refinamiento.

La realidad del serving hoy (verificada en el código) acota lo que es posible
sin reescribir infraestructura:

- El catálogo de serving es **100% estático**: `LlmRuntimeConfig` es `frozen` y
  se carga una vez con `@lru_cache(maxsize=1)`; los clientes (`llm_client`,
  `embedder`, `reranker`) son singletons construidos en el lifespan y viven en
  `app.state` hasta el shutdown. No hay setter ni rebuild en caliente
  (ADR-013 D3: la orquestación del servidor es ajena al cliente).
- En cambio, `LlmClient.complete()` **ya acepta parámetros por request**
  (`max_tokens`, `temperature`, `thinking`, `timeout_s`): mandar un mensaje
  ad-hoc a un modelo con params elegidos NO requiere reconfig.
- `_wants_real_llm(settings)` decide fake vs real: el singleton es
  `FakeLlmClient` salvo `LLM_BACKEND=vllm` o `ENVIRONMENT=production`. Un
  `complete()` ad-hoc contra el Fake del lifespan revienta (sus respuestas son
  pre-encoladas) → el playground es genuinamente útil **solo contra serving
  real**.

Esto parte el control plane en dos mitades con riesgo muy distinto: **leer +
mandar mensajes ad-hoc** (aditivo, cero mutación de estado global) vs **cambiar
el serving que usa el producto en caliente** (mutar singletons + orquestar
procesos). Este ADR resuelve la primera; la segunda se difiere.

## Decisión

### D1 — Fase 1: playground aislado (este ADR)

Dos endpoints aditivos en `app/api/v1/admin.py`, gateados con `CurrentAdmin`:

1. **`GET /v1/admin/serving`** — estado read-only del serving: backend
   (`fake`/`vllm`), `is_real`, salud agregada, y por modelo `served_name`,
   `role`, `quantization`, `tool_parser`, `max_model_len`, `healthy`,
   `default_thinking`. Más `embedder`/`reranker`. **Sin `base_url` ni
   connection strings.**
2. **`POST /v1/admin/playground`** — completion ad-hoc **sync** que llama
   `llm_client.complete()` **directo** (NO `route()`, NO `run_tool_loop()`),
   **sin `DbSession`** en la firma → cero `ChatSession`, `conversation_turns`,
   memoria episódica o consolidación. Aislamiento total respecto del producto.

El **"modo bajo rendimiento"** es un preset de parámetros sobre el contrato
existente (`max_tokens≈256`, `temperature≈0.2`, `thinking=False`,
`timeout_s=30`): es la capacidad natural de `complete()` por request, **no muta
estado global**. El toggle es **por mensaje**, no una configuración del producto.

Contra `FakeLlmClient` (dev default) el endpoint responde **409** explícito
("serving real no disponible") en vez de intentar `complete()` y reventar en 500.
En dev el panel usa handlers MSW para que la pantalla sea usable mock-first.

Wire **sync JSON, no SSE**: el SSE de `/chat/stream` es *fake-streaming*
(trocea el turno ya computado), así que para un probe de un turno no aporta y
suma complejidad; además el sync expone `prompt_tokens`/`completion_tokens`/
`latency_ms` que el chat de producto no devuelve.

### D2 — Fase 2: control global runtime (NO en este ADR, diferido)

Cambiar en caliente el modelo que usa un modo del producto, el backend
(fake↔vllm), `max_model_len`/quant, o la topología `LLM_SERVING`, queda **fuera
de alcance**. Requiere infra que hoy no existe: invalidar/mutar el `lru_cache`
de config, reconstruir los singletons de `app.state` async-safe, y arrancar/parar
procesos de serving (orquestación de servidor que el cliente no toca, ADR-013
D3). Persistir overrides exigiría tabla nueva (regla #3) o escribir
`ynara.config.json` (gateado). Se difiere a un ADR futuro.

### D3 — Frontera

Fase 1 = **read + send** (read-only sobre el estado global del serving). Fase 2 =
**write** sobre ese estado. La pantalla del playground muestra "bajo rendimiento"
como toggle **per-request**; un futuro "fijar bajo rendimiento para todo el
producto" es fase 2.

## Consecuencias positivas

- Puramente aditivo: cero migraciones, cero mutación de singletons, cero riesgo
  sobre el serving del producto. No cae bajo regla #3 (no toca memoria ni
  `alembic/versions/`).
- El operador ve fallos LLM **reales** (no el fallback "degraded" maquillado de
  `/chat`): es un probe del modelo crudo, ideal para diagnosticar serving.
- Reusa todo el wiring de auth admin (`CurrentAdmin`) y el patrón de
  `/v1/admin/system`. La pantalla reusa el design system del panel.
- Entrega lo pedido (elegir modelo + bajo rendimiento + chat de prueba) sin la
  superficie de riesgo del control global.

## Consecuencias negativas

- El playground es útil **solo con `LLM_BACKEND=vllm`** (o serving real): contra
  el Fake responde 409. Es una limitación honesta, no un bug.
- No valida la ruta de producto (memoria/tools/router) — por diseño es un probe
  del modelo pelado, no un end-to-end del chat real.
- Cambiar el serving global sigue exigiendo restart (eso es fase 2).

## Alternativas descartadas

- **Reusar `route()` / `/v1/chat`**: arrastra memoria, tool-loop, sesión y
  consolidación, y enmascara errores como `degraded`. El playground quiere el
  modelo crudo. Descartada.
- **SSE token-streaming en v1**: el SSE actual es fake-streaming (no hay
  token-streaming real desde el modelo); para un turno no aporta y complica el
  wire. Si fase 2 trae streaming real desde vLLM, se agrega
  `POST /v1/admin/playground/stream`. Descartada para v1.
- **Branch de Fake en el endpoint (eco/placeholder)**: meter lógica de Fake en
  un endpoint de prod. Descartada: mejor un 409 explícito + doc de que el
  playground requiere serving real (el mock vive en MSW, lado cliente).
- **Reconfig en caliente ya (fase 2 directo)**: mutar singletons + orquestar
  serving es un ADR aparte por scope y riesgo. Descartada para ahora.

## Privacidad / seguridad (regla #4)

- **Nunca** exponer `base_url` de los endpoints de serving (puede llevar
  host/creds). `GET /v1/admin/serving` expone backend + served_names, no URLs.
- **Nunca** ecoar el body crudo de un `LlmError`: el mapeo a status usa solo
  `type(exc).__name__`, jamás `str(exc)` con payload.
- El playground **no persiste nada**: sin DB, sin turnos cifrados, sin logs de
  contenido. El input del operador no toca la memoria del producto.

## Relación con otros ADRs

- **Materializa la fase 1** del control plane de
  [ADR-017](./ADR-017-admin-app-observabilidad-control-plane.md) D7.
- **Refina** [ADR-013](./ADR-013-serving-endpoints-config.md) y
  [ADR-014](./ADR-014-serving-ollama-gguf-16gb.md): se apoya en que el serving
  es estático al boot y que `complete()` parametriza por request; el control
  global runtime (que sí tocaría su contrato) queda diferido a fase 2.
