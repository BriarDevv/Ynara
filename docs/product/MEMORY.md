# MEMORY.md — Modelo de memoria de Ynara

Memoria es el core del producto. Esta doc cubre **qué se guarda**,
**cuánto vive**, **quién puede tocarla** y **qué derechos tiene el
usuario**.

## Las 3 capas

### Semántica
- Qué: hechos persistentes sobre el usuario.
- Cómo se guarda: registros de Mem0 OSS v2 en `semantic_memory`,
  con embedding bge-m3 (1024-dim) sobre pgvector.
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
   `procedural_memory` solo se tocan con tests + 2 aprobaciones
   humanas (regla #3 de `AGENTS.md`).
4. **Data del usuario nunca sale del perímetro** (regla #4 de
   `AGENTS.md`).

## Derechos del usuario

El usuario puede:

- **Ver toda su memoria.** Endpoint `GET /v1/memory` (filtrable por
  capa).
- **Editar entradas individuales.** `PATCH /v1/memory/{id}`.
- **Borrar entradas individuales.** `DELETE /v1/memory/{id}`.
- **Borrar todo.** `DELETE /v1/memory` con confirmación + dry-run.
  Script equivalente: `scripts/reset-memory.sh`.
- **Pausar.** Activar modo "no escribas memoria" temporalmente.
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

## Open questions

<!-- TODO: cerrar -->
- Cómo manejamos "olvido por decaimiento" en procedural memory.
- Retención de memoria episódica en modo Bienestar — ¿más corta por
  defecto?
- Encriptación en reposo a nivel campo (no solo a nivel disco).
