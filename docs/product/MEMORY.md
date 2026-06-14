# MEMORY.md — Modelo de memoria de Ynara

Memoria es el core del producto. Esta doc cubre **qué se guarda**,
**cuánto vive**, **quién puede tocarla** y **qué derechos tiene el
usuario**.

## Las 3 capas

### Semántica
- Qué: hechos persistentes sobre el usuario.
- Cómo se guarda: storage propio (engine in-house, [ADR-010](../architecture/adrs/ADR-010-memory-architecture-v2.md))
  en `semantic_memory` — `content` cifrado AES-256-GCM + embedding
  bge-m3 (1024-dim) en claro sobre pgvector.
- Cuánto vive: indefinido hasta que el usuario lo borre.
- Quién la actualiza: solo Qwen 3.5-9B (modos Productividad +
  Memoria), siempre vía Celery async.

### Episódica
- Qué: resúmenes de conversaciones pasadas, recuperables por
  contexto.
- Cómo: tabla `episodic_memory` con embedding del resumen + JSONB
  con metadata (modo, duración, tópicos).
- Cuánto vive: 12 meses por defecto, configurable por el usuario.
- Quién la actualiza: Qwen al cerrar sesión (async Celery).

### Procedural
- Qué: preferencias y patrones de comportamiento del usuario.
- Cómo: tabla `procedural_memory` con JSONB estructurado.
- Cuánto vive: indefinido. Decae si el patrón deja de observarse.
- Quién la actualiza: Qwen vía pipeline de Celery + heurísticas.

Detalle de tablas en `apps/backend/docs/MODELS.md`.

## Reglas duras

1. **Solo Qwen escribe memoria.** Gemma nunca, por diseño.
2. **Consolidación asíncrona.** La extracción/escritura nunca está en
   el path de respuesta al usuario.
3. **Tablas sagradas.** `semantic_memory`, `episodic_memory`,
   `procedural_memory` solo se tocan con tests + 1 aprobación humana
   explícita (regla #3 de `AGENTS.md`).
4. **Data del usuario nunca sale del perímetro** (regla #4 de
   `AGENTS.md`).

## Derechos del usuario

El usuario puede:

- **Ver toda su memoria.** Endpoint `GET /v1/memory` (filtrable por
  capa).
- **Editar entradas individuales.** `PATCH /v1/memory/{id}`.
- **Borrar entradas individuales.** `DELETE /v1/memory/{id}`.
- **Borrar todo.** `GET /v1/memory/wipe` (preview/dry-run por capa) +
  `POST /v1/memory/wipe` (execute con `confirm` per-layer). Ya disponible.
  Script equivalente: `scripts/reset-memory.sh`.
- **Pausar.** Activar modo "no escribas memoria" temporalmente.
  *(pendiente — endpoint `PATCH /v1/memory/settings` no implementado aún.)*
- **Exportar.** `GET /v1/memory/export` devuelve JSON estructurado
  con todo. Script: `scripts/export-user-data.sh`.

## Audit log

Cada operación sobre memoria queda registrada:
- Timestamp UTC.
- `user_id`.
- Operación: read / write / update / delete.
- Origen: modelo (qwen/gemma) + modo activo + tool si aplica.
- Hash de la entrada afectada.

Retención del audit log: 24 meses.

## Borrado físico vs lógico

- Borrado por el usuario es **borrado físico**. Se ejecuta `DELETE`
  en SQL, no soft-delete.
- Backup más reciente puede contener la entrada borrada durante
  hasta 30 días — política comunicada explícitamente en la UI.

## Políticas operacionales

Las tres decisiones operacionales de memoria (decay, retention
diferenciada, encriptación a nivel campo) están cerradas en
[`ADR-007`](../architecture/adrs/ADR-007-memory-decay-retention-encryption.md).
Resumen:

### Decay en procedural memory

Decay exponencial con threshold: `confidence *= 0.9` cada 14 días
sin reforzar. Cuando `confidence < 0.3`, la entrada queda `stale=true`
y el router no la inyecta automáticamente — el agente puede preguntar
al usuario antes de actuar. Borrado físico cuando `confidence < 0.1` Y
`last_reinforced_at > 90 días`.

Los 5 thresholds (`decay_interval_days`, `decay_factor`,
`stale_threshold`, `hard_delete_threshold`, `hard_delete_min_days`) son
**config-driven** vía `ynara.config.json[memory]` (no hardcodeados): los
parsea `app/memory/config.py` (mismo patrón fail-fast que
`app/llm/config.py`) y `app/workflows/decay.py` los lee de ahí. Si el
bloque falta o trae valores parciales, el loader cae a los defaults de
ADR-007 D1 (los de arriba), así un config viejo no rompe el job (#211).

### Retention de memoria episódica

Default: 12 meses. Modo **Bienestar**: 6 meses (configurable
1-12 meses por usuario via `PATCH /v1/memory/settings` — pendiente). Flag
`is_sensitive=true` gatilla audit log diferenciado y export anidado.

### Encriptación a nivel campo

`semantic_memory.content` y `episodic_memory.summary` cifrados con
AES-256-GCM. Key derivada por usuario via HKDF-SHA256 sobre master
key server-side. Embeddings sin cifrar (necesarios para pgvector).
`procedural_memory.value` queda en JSONB plain — son preferencias
no sensibles. Helper: `apps/backend/app/core/crypto.py`.

Detalle completo, alternativas descartadas y mitigaciones en el ADR.
