# ADR-007: Políticas operacionales de memoria (decay, retention diferenciada, encriptación a nivel campo)

## Estado
Aceptado

## Fecha
2026-05-19

> **NOTA DE ACTUALIZACIÓN (post-aceptación):** la cadencia del worker de decay
> se corrigió de **"diaria"** a **por-intervalo**: el worker decae las entradas
> no reforzadas en el último `DECAY_INTERVAL_DAYS` (default 14 días), NO todos
> los días. Sin una columna de tracking, una corrida diaria con `confidence *=
> 0.9` compondría el decay día a día (≈0.9^días) en vez de aplicarlo una vez por
> intervalo. La cadencia por-intervalo es la única forma correcta sin compounding;
> justificación completa en `apps/backend/app/workflows/decay.py`. El cuerpo
> histórico de abajo (D1, "worker Celery diario", "Beat de Celery diario") se
> conserva tal cual fue aceptado.

## Contexto

[`docs/product/MEMORY.md`](../../product/MEMORY.md) sección "Open questions" declaraba tres decisiones operacionales pendientes que afectan el schema de las tablas sagradas (`semantic_memory`, `episodic_memory`, `procedural_memory`) y el flujo de lectura/escritura:

1. **Decay en procedural memory**: cómo se modela "el patrón deja de observarse" sin perder calidez ni dejar data stale activa.
2. **Retention diferenciada en Bienestar**: si la memoria episódica generada en modo Bienestar debe tener TTL más corto que los 12 meses default por privacidad emocional.
3. **Encriptación a nivel campo**: si el contenido textual de memoria debe cifrarse en columna (no solo a nivel disco) para defensa contra leaks de DB.

Las tres tocan campos concretos que van a aparecer en la migración Alembic inicial. Resolverlas ahora — antes de crear los modelos SQLAlchemy concretos — evita migraciones extras y se ahorra el costo de tablas sagradas (regla #3 de [`AGENTS.md`](../../../AGENTS.md): 1 aprobación humana explícita por cada cambio de schema).

## Decisión

### D1 — Decay exponencial con threshold en procedural memory

- Cada entrada de `procedural_memory` lleva `confidence: float` (0-1) y `last_reinforced_at: timestamptz`.
- Un worker Celery diario recorre las entradas y aplica decay exponencial: `confidence *= 0.9` cuando pasaron `decay_interval_days` desde `last_reinforced_at`.
- **`decay_interval_days = 14` por default** — alineado con ciclos quincenales del usuario.
- Cuando `confidence < 0.3`, la entrada queda marcada como **`stale = true`**. El router LLM no la inyecta automáticamente al prompt; el agente puede decidir preguntar al usuario ("¿seguís prefiriendo X?") antes de actuar sobre data vieja.
- **Reforzar** una entrada (`procedural.upsert` con el mismo `key`) resetea `confidence = 1.0`, `last_reinforced_at = now()`, `stale = false`.
- **Borrado físico** cuando `confidence < 0.1` **y** `last_reinforced_at` > 90 días: doble criterio para evitar borrar entradas que decayeron por baja interacción del usuario en general, no por desinterés en el patrón.

### D2 — Retention diferenciada en Bienestar via flag `is_sensitive`

- Campo `is_sensitive: boolean` en `episodic_memory` (default `false`).
- Cuando el modo activo es `bienestar`, el worker de consolidación setea `is_sensitive = true` en la entrada generada.
- **Retention por flag**:
  - Default (productividad, estudio, vida, memoria): **12 meses**.
  - `is_sensitive = true`: **180 días** default (≈6 meses), configurable por usuario via `PATCH /v1/memory/settings`. Rango aceptado: **30-365 días** (≈1-12 meses, donde 1 mes = 30 días). El código (constraint `users.retention_sensitive_days BETWEEN 30 AND 365`) usa días; la narrativa de meses es aproximada para comunicación al usuario.
- `is_sensitive = true` también gatilla:
  - Audit log con flag `sensitive=true` para queries diferenciadas (regla del repo: audit log de 24 meses sobre toda operación de memoria).
  - `GET /v1/memory/export` separa las entradas sensibles en un JSON anidado distinto, para que el export sea inspecionable sin mezclar registros emocionales con el resto.

### D3 — Encriptación a nivel campo: AES-256-GCM con key derivada por usuario

- **Campos cifrados**: `content` (semantic) y `summary` (episodic).
- **`procedural_memory.value`** queda en JSONB plain — son preferencias estructuradas no sensibles por diseño (ej: `{"voseo": true, "pomodoro_minutes": 25}`).
- **Embeddings** (`vector(1024)`) quedan **sin cifrar** — no son reversibles a texto crudo y son necesarios para búsqueda por similitud vía pgvector.
- **Algoritmo**: AES-256-GCM con nonce aleatorio de 96 bits por record.
- **Storage**: `BYTEA` con layout `nonce (12B) || ciphertext (var) || auth_tag (16B)`. Overhead fijo: 28 bytes por record.
- **Key derivation**: HKDF-SHA256 sobre master key server-side. Info: `b"ynara-memory-v1:" + str(user_id).encode()`. Output: 32 bytes (AES-256).
- **Master key**: env var `MEMORY_ENCRYPTION_MASTER_KEY` (base64 de 32 bytes random). Nunca commiteada (regla #2 de `AGENTS.md`).
- **Helper**: `apps/backend/app/core/crypto.py` con `encrypt_for_user(user_id: UUID, plaintext: str) -> bytes` y `decrypt_for_user(user_id: UUID, ciphertext: bytes) -> str`. Los wrappers de memoria invocan al helper en read/write.
- **Rotación de master key**: TODO para V2. Para MVP, master key estática.

## Consecuencias positivas

- **Calidez sin data stale activa**: el decay exponencial cumple "no olvido abrupto" del posicionamiento conversacional. El threshold gatilla un check explícito antes de actuar sobre data vieja.
- **Privacidad emocional con flexibilidad**: retention más corta en Bienestar por default sin perder UX para usuarios que valoran continuidad. El usuario decide.
- **Defensa contra leak de DB**: aún con acceso directo a SQL (injection, backup leak, dump no autorizado), `semantic_memory.content` y `episodic_memory.summary` no son legibles sin el master key + `user_id`. Alineado con el posicionamiento "infra propia + privacidad" del informe técnico (§2.6).
- **Blast radius acotado**: key-per-user vía HKDF significa que comprometer el cifrado de un user no compromete a los demás (siempre que el master key no se filtre).

## Consecuencias negativas

- **Latencia de lectura**: cada lectura cifrada agrega un descifrado in-memory. Para un turn típico (top-3 semantic + top-2 episodic = 5 records): ~5 operaciones AES-GCM, negligible en CPU moderno (<1ms total).
- **Búsquedas por contenido textual prohibidas**: no se puede `LIKE '%...%'` sobre `content` o `summary`. Workaround: búsqueda por embedding (camino canónico del producto). Si en el futuro hace falta full-text search, evaluar PgCrypto con searchable encryption o tokens HMAC indexados.
- **Worker de decay agrega un job recurrente**: complejidad operativa marginal. Beat de Celery diario.
- **Master key como single point of failure**: si se pierde, todo el contenido cifrado queda inrecuperable. Mitigación: backup de la master key en gestor de secretos del equipo (no en el repo); para V2, considerar key escrow o split.

## Mitigaciones

- **Tests de regresión sobre `app/core/crypto.py`**: roundtrip determinístico (excepto el nonce), manejo de nonce, manejo de wrong-key (debe lanzar `InvalidTag`), edge cases (empty string, unicode largo, payload > 1MB).
- **Decay aislado por feature flag** durante MVP: el worker corre y actualiza `confidence`, pero `stale = true` puede gatearse con un flag `ENABLE_PROCEDURAL_DECAY_GATING` hasta que el flow del agente esté listo para actuar sobre el flag. Reduce blast radius si el algoritmo necesita ajuste.
- **`decay_interval_days` configurable** en `ynara.config.json[memory]`: si 14 días resulta muy agresivo o muy laxo, se ajusta sin migración.
- **Tests de cifrado en el wrapper de memoria**: además del helper unitario, los tests de integración de `semantic.add` / `semantic.search` deben verificar que `content` queda en `BYTEA` cifrado y que la lectura descifra correctamente.

## Alternativas descartadas

### Decay
- **Hard cutoff por TTL**: más simple pero rompe calidez — el agente pierde preferencias sin previo aviso.
- **Sin decay automático**: traslada el problema al agente, que tiene que detectar contradicciones. Frágil.

### Retention en Bienestar
- **30 días estrictos en Bienestar**: privacidad fuerte pero rompe UX cuando el usuario referencia algo de hace 2 meses.
- **12 meses uniforme con solo flag `is_sensitive`**: no diferencia el modo más íntimo, pierde la oportunidad de privacy-by-default.

### Encriptación
- **PgCrypto con key compartida server-side**: la key vive en una sola variable; si se filtra, todo el universo de usuarios queda descifrable. Peor blast radius que key-per-user.
- **Disk-level encryption solo**: no protege contra SQL injection ni backup leak. Subóptimo para un producto que vende "infra propia + privacidad" como ventaja defensiva (informe técnico §2.6).
- **Field-level encryption sobre embeddings también**: hace imposible la búsqueda semántica (que es lo que pgvector existe para hacer). No es opción.
- **AES-CBC en lugar de GCM**: GCM da autenticidad además de confidencialidad (rechaza ciphertext modificado). CBC requiere MAC separado. GCM es el default moderno.

## Impacto en archivos del repo

### `docs/product/MEMORY.md`
La sección "Open questions" (`MEMORY.md:76-82`) se cierra. Se reemplaza por un puntero a este ADR + las decisiones resumidas.

### Esquema (PR B — migración Alembic inicial)

Las tablas sagradas quedan así (campos relevantes a este ADR; columnas comunes `id/created_at/updated_at/user_id` van del `Base + UUIDPKMixin + TimestampMixin`):

- **`semantic_memory`**:
  - `content BYTEA NOT NULL` (cifrado AES-GCM)
  - `content_embedding vector(1024) NOT NULL` (plain)
- **`episodic_memory`**:
  - `summary BYTEA NOT NULL` (cifrado AES-GCM)
  - `summary_embedding vector(1024) NOT NULL` (plain)
  - `is_sensitive BOOLEAN NOT NULL DEFAULT false`
  - `retention_days INTEGER NOT NULL DEFAULT 365` (sobrescrito a 180 cuando `is_sensitive=true` al insert; configurable por usuario via settings)
- **`procedural_memory`**:
  - `value JSONB NOT NULL` (plain — preferencias no sensibles)
  - `confidence REAL NOT NULL DEFAULT 1.0`
  - `last_reinforced_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `stale BOOLEAN NOT NULL DEFAULT false`

Detalle completo de FKs, índices (HNSW sobre embeddings), y constraints en [`apps/backend/docs/MODELS.md`](../../../apps/backend/docs/MODELS.md) cuando arranque el PR A del plan T1.

### `apps/backend/app/core/crypto.py`
Helper nuevo (no existe hoy) con la API descrita en D3. Tests en `tests/core/test_crypto.py`. *(Nota post-aprobación: implementado y mergeado en PR C.)*

### `ynara.config.json[memory]`
Sección nueva con:

```json
{
  "memory": {
    "decay_interval_days": 14,
    "decay_factor": 0.9,
    "stale_threshold": 0.3,
    "hard_delete_threshold": 0.1,
    "hard_delete_min_days": 90,
    "retention_default_days": 365,
    "retention_sensitive_days": 180,
    "retention_sensitive_min_days": 30,
    "retention_sensitive_max_days": 365
  }
}
```

Por regla #1 de `AGENTS.md`, el PR que agregue esta sección requiere OK humano explícito (toca `ynara.config.json`).

## Links

- [`docs/product/MEMORY.md`](../../product/MEMORY.md) — modelo de memoria.
- [`ADR-002`](./ADR-002-gemma-qwen-dual-stack.md) — dual stack Gemma + Qwen.
- [`ADR-003`](./ADR-003-mem0-vs-letta.md) — Mem0 OSS v2 como engine. *(Superseded por ADR-010.)*
- [`ADR-004`](./ADR-004-postgres-pgvector-vs-pinecone.md) — Postgres + pgvector.
- [`docs/architecture/informe-tecnico.pdf`](../informe-tecnico.pdf) §1.5 (flow turn-por-turn) y §2.5 (BD).
