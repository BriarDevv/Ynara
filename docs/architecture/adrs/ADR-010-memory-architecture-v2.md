# ADR-010: Arquitectura de memoria v2 — engine in-house sobre storage cifrado propio (supersede ADR-003)

## Estado
Aceptado

## Fecha
2026-05-30

## Contexto

[ADR-003](./ADR-003-mem0-vs-letta.md) decidió **Mem0 OSS v2 como engine de memoria semántica**, con custom hooks propios para las capas episódica y procedural. Esa decisión se tomó antes de que cerráramos el cifrado a nivel campo ([ADR-007 D3](./ADR-007-memory-decay-retention-encryption.md)) y antes de que existiera el helper `app/core/crypto.py` (PR C). Hoy hay una **contradicción estructural** entre las dos decisiones que hay que resolver antes de implementar M7 (Tool `memory.*`).

El problema concreto, verificado contra el código del repo:

- **Mem0 fija su propio DDL** (`id` / `vector` / `payload`-JSONB) y escribe el contenido del hecho **en texto plano** en ese payload. No expone un hook *pre-store* para cifrar antes del INSERT.
- **El pipeline de Mem0 necesita plaintext persistido**: extracción de hechos (LLM/NER), deduplicación, y `UPDATE`/`MERGE` comparan texto contra texto. Con `content` cifrado en `BYTEA` y **nonce aleatorio por record** (`crypto.py:103`), dos hechos idénticos dan blobs distintos — cualquier dedup o merge *at-rest* es imposible por diseño criptográfico.
- **Mem0 mantiene un SQLite de historia de conversación en claro**, fuera de nuestras tablas sagradas y fuera del cifrado.

Es decir: Mem0 como **engine de storage** es incompatible con el moat (cifrado a nivel campo, tablas sagradas, master key server-side). Adaptarlo significaría forkear su core (peor que construir in-house) o renunciar al cifrado (matar el moat, ya descartado en ADR-007).

Lo que abarata reemplazarlo: **el sunk cost de Mem0 es casi nulo**. Es una línea en `apps/backend/pyproject.toml:26` (`mem0ai>=0.1.0`) más tres docs (ADR-003, `MEMORY.md`, roadmap §5.1). **No hay storage de Mem0 escrito**: los wrappers `app/memory/{semantic,episodic,procedural}.py` son stubs `NotImplementedError` (`semantic.py:21`, etc.). Y ya tenemos la prueba de que el equipo sabe construir abstracciones limpias e inyectables: toda la capa LLM está hand-rolled detrás de Protocols `runtime_checkable` (`llm/clients/base.py`, `embedding.py`, `pool.py`, `resilient.py`), con Fakes deterministas para tests. La memoria stub es un lienzo en blanco, no deuda.

> **Nota post-aprobación:** M7 completado; los wrappers tienen implementación real con storage cifrado propio; los docstrings ya no referencian Mem0.

Cuatro investigaciones de SOTA 2025-2026 (frameworks de memoria, vector stores, pipeline de retrieval, modelos de embedding) más una validación arquitectónica contra el repo confirman el encuadre: **ningún framework mainstream** (Mem0, Letta/MemGPT, Zep/Graphiti, LangMem, cognee) soporta cifrado a nivel campo nativo en su capa de storage; todos asumen texto plano y delegan la seguridad al cloud o al motor de DB. Por lo tanto la decisión no es "qué framework comprar" sino "cómo construir la inteligencia propia detrás de Protocols, usando los frameworks como referencia de algoritmo, nunca como dependencia de storage".

> **Nota de fuentes**: las afirmaciones de SOTA (MTEB/BEIR, LongMemEval, benchmarks pgvectorscale) provienen de research con WebSearch a mayo 2026 más conocimiento de entrenamiento a enero 2026. No se re-verificaron online al escribir este ADR; los números puntuales deben tratarse como órdenes de magnitud, no como cifras contractuales. Las afirmaciones sobre el repo (stubs, DDL, crypto, Protocols) **sí** están verificadas contra el código.

## Decisión

Ynara **ownea el ciclo de vida completo de la memoria**: storage cifrado propio + capa de inteligencia/retrieval propia, ambos detrás de Protocols inyectables. Mem0 baja de **engine de storage** a, a lo sumo, **referencia de algoritmo** (o `extractor` in-memory en M8); nunca toca el storage. Este ADR **supersede ADR-003** (en lo que ADR-003 cubría: Mem0 como engine de storage de la capa semántica) y deja intactos ADR-004, ADR-007, ADR-008 y ADR-009.

### D1 — Storage: lo owneamos sobre Postgres + pgvector + tablas cifradas (ADR-004 reforzado)

- **El store es Postgres 16 + pgvector**, las tablas sagradas ya creadas (`semantic_memory`, `episodic_memory`, `procedural_memory`, migración PR B). No se introduce ninguna vector DB dedicada.
- La razón central **no es solo performance, es compatibilidad con el cifrado**: el server tiene el master key en memoria (`MEMORY_ENCRYPTION_MASTER_KEY`), cifra al escribir y descifra al leer *in-process*; el `content`/`summary` cifrado convive en la **misma fila transaccional** que el embedding en claro. Ninguna vector DB dedicada (Qdrant, Milvus, Weaviate, LanceDB) puede replicar esto sin romper ACID con el relacional o sin sacar los datos de Postgres — y todas guardan su payload sin cifrado a nivel campo, con lo cual el trade-off de cifrado vs búsqueda por texto es **idéntico** al de Postgres, pero perdiendo el ACID gratis.
- **Sharding por `user_id`**: el camino de escalado es particionado `LIST PARTITION` por `user_id` (cada partición con su propio índice HNSW; el planner hace pruning automático al filtrar por `user_id`). Ynara nunca hace búsqueda cross-user, así que el espacio vectorial particiona limpio por usuario. Esto se documenta como **camino de escalado, no se implementa en M7** (el corpus MVP es chico).
- **`pgvectorscale` / StreamingDiskANN** entra como **upgrade in-place additive** cuando un usuario individual supere ~1-2M vectores o se mida presión de RAM en el build HNSW: pagina el grafo en disco (reduce footprint de RAM con SBQ), es un `ALTER INDEX` por partición, **no** migración de stack ni de datos. Esto extiende el rango cómodo sin salir del relacional y neutraliza el único argumento serio para irse a una vector DB dedicada. **Regla práctica**: no salir de Postgres hasta que el query vectorial sea el bottleneck *medido* (profiling real), no el bottleneck *temido*.
- **Costo de build del índice**: el bottleneck a vigilar no es solo el query — para un corpus que crece, el **build/insert incremental del HNSW** (y su uso de RAM) suele saturar antes que la latencia de query. El profiling debe medir ambos (build y query) antes de decidir cualquier upgrade.
- **Mem0 se remueve como dependencia de storage.** A elección del implementador de M8: o se saca `mem0ai` de `pyproject.toml`, o se lo aísla detrás de un adapter que use **solo** su extractor de hechos in-memory (nunca su store, nunca su SQLite de historia). Default recomendado: removerlo y construir la extracción in-house (ver D4).

### D2 — Pipeline de retrieval compatible con cifrado: vector → descifrar top-K → rerank

El cifrado *at-rest* mata BM25/full-text/`LIKE` server-side sobre `content`/`summary` (ADR-007 ya lo declara), pero **no** mata el vector search: los embeddings van en plano. El pipeline canónico, el mejor **compatible con cifrado at-rest** para el threat model de Ynara, es:

**Indexación (write path, async vía Celery — regla #2 de `MEMORY.md`):**
1. Texto plano llega al server (nunca sale del perímetro, regla #4).
2. *(M8, opcional)* contextual retrieval: prepend 2-3 oraciones de contexto generadas por Qwen/Gemma on-prem antes de embeddear.
3. Embeddear con el modelo de D3 (vector en claro, 1024 floats).
4. Cifrar `content`/`summary` con `encrypt_for_user()` (`crypto.py`).
5. Persistir en la misma transacción ACID: `embedding` en claro, `content` cifrado.

**Retrieval (read path):**
1. Embeddear el query del usuario.
2. ANN search en pgvector HNSW cosine → **top-K candidatos** (K≈20-50). Solo toca embeddings en claro, O(log N).
3. **Descifrar el top-K in-process** con `decrypt_for_user()` (el server tiene la key; el plaintext existe efímeramente en RAM, nunca se persiste).
4. **Cross-encoder reranking** sobre los pares `(query, plaintext_chunk)` descifrados → top-N (5-10).
5. Inyectar top-N al LLM.

- **Honestidad sobre el costo del cifrado**: este pipeline es el **mejor compatible con cifrado at-rest**, no es equivalente a un híbrido completo. La evidencia pública de mejores resultados (p.ej. Anthropic Contextual Retrieval) corresponde a pipelines que **incluyen BM25**, que acá renunciamos por el cifrado. El costo real es la **pérdida del término léxico / exact-match** (nombres propios, términos técnicos exactos): el cross-encoder rerank lo **mitiga, no lo anula**. Si en producción se mide pérdida de casos exact-match, la opción de blind-index (abajo) está documentada.
- **Reranker on-prem (a fijar en M8)**: candidatos `Qwen3-Reranker-0.6B` (misma familia que el embedder candidato de D3, mismo runtime vLLM, Apache 2.0), `bge-reranker-v2-m3` (278M, si se prioriza CPU/latencia), o `mxbai-rerank-base-v2` (0.5B, Apache 2.0, máxima calidad). La elección del peso real se difiere a M8; en M7 solo se fija el **contrato**.
- **Pluggable vía Protocol**: se define un `Reranker` Protocol `runtime_checkable` espejando `LLMClient`/`EmbeddingClient`, con un `FakeReranker` determinista **ahora** (M7, passthrough estable) y la implementación real diferida (M8), exactamente como `FakeLlmClient` (M2) precedió a `VllmClient` (M3) y `FakeEmbeddingClient` precedió al `VllmEmbeddingClient`.
- **Keyword / blind-index: decidido NO para M7/M8.** El nonce aleatorio por record impide cualquier índice determinista/HMAC sobre `content` tal como está hoy. Recuperar exact-match keyword requeriría un esquema HMAC **separado** del GCM actual (`HMAC(token_normalizado, blind_index_key)` en tabla auxiliar `memory_token_hashes`, con `blind_index_key` distinta de la encryption_key). Se documenta como **opción futura** (ya anticipada en ADR-007 "Consecuencias negativas"), a evaluar solo si el retrieval vectorial + rerank demuestra perder casos de nombre propio / término técnico exacto. **No bloquea nada.**

### D3 — Embeddings: bge-m3 vigente; Qwen3-Embedding-0.6B como candidato a validar con A/B en M8; `Vector(1024)` se mantiene

- **Se mantiene `Vector(1024)`** (`EMBEDDING_DIM = 1024` en `models/memory.py:48` y `embedding.py:28`). 1024 es el sweet spot calidad/storage/velocidad para memoria personal; doblar a 2048 duplica storage y compute sin ganancia proporcional de recall. **No se toca el schema sagrado.**
- **bge-m3 (ADR-008) sigue siendo el default vigente** y es 100% válido para M7. ADR-008 **no se supersede**: el embedder real ni siquiera está cableado todavía (solo `FakeEmbeddingClient`).
- **Candidato a evaluar en M8 (NO decidido)**: **`Qwen3-Embedding-0.6B`** (Alibaba, Apache 2.0) es atractivo por lo estructural: salida configurable a **1024 dims** vía MRL (drop-in sobre el schema, **sin re-migración sagrada**), VRAM ~igual a bge-m3, vLLM nativo, contexto 32K (relevante para `summary` episódicos largos), y un **reranker hermano** `Qwen3-Reranker-0.6B`. **Pero la migración se gatea a una eval A/B real, no a una fecha**, por dos trampas que no están medidas para nuestro caso:
  - **MRL truncado a 1024 degrada recall** (la salida nativa del modelo es mayor; truncar no es gratis). La magnitud de esa degradación para corpus personal multilingüe rioplatense **no está medida**.
  - El modelo es **instruction-aware**: el recall depende del *instruction prefix* correcto — una fuente de regresión silenciosa que bge-m3 no tiene.
  - **Gate**: M8 mide `recall@k` con Qwen3 MRL-1024 truncado **vs** bge-m3 full sobre **corpus real de Ynara** (no MTEB agregado). Si no se mide, **no se migra**: el sweet spot actual (bge-m3) ya funciona.
- **Costo de esa migración si se aprueba**: NO es migración de schema (sigue `Vector(1024)`), **es migración de DATOS** — los vectores de bge-m3 y Qwen3 no son comparables, hay que **re-embeddear todo el corpus** en ventana de mantenimiento. Para el corpus MVP (chico) son minutos.
- **NO escalar a Qwen3-Embedding-4B/8B** mientras Gemma + Qwen LLM compartan la RTX 4080 Super (ADR-009): el 0.6B da la mayor parte de la ganancia con impacto mínimo de VRAM. Reservar variantes grandes para cuando haya GPU dedicada.

### D4 — Inteligencia de memoria (extracción / dedup / resolución de conflictos): lógica propia in-process

- **Se construye in-house**, detrás de un Protocol `MemoryEngine` (`extract` / `consolidate` / `search`) que espeja `LLMClient`. Razón: toda operación que necesita plaintext (extraer hechos, deduplicar, mergear, resolver conflictos) **debe** correr in-process sobre texto descifrado o sobre similitud de embeddings en claro — porque el nonce aleatorio rompe cualquier comparación textual *at-rest*. Esto es exactamente lo que vuelve estructuralmente incompatible a cualquier engine externo que asume storage plaintext, y exactamente lo que un engine propio resuelve natural.
- **Extracción de hechos**: se le pide a **Qwen** (modo agente, único que escribe memoria — regla #1 de `MEMORY.md`) la extracción en el patrón `ADD/UPDATE/DELETE/NOOP` (el mismo que el roadmap §5.1 ya asume). Mem0 puede usarse como **referencia del prompt/heurística**, o aislarse como `extractor` in-memory que recibe plaintext y devuelve hechos — **nunca persiste**.
- **Dedup / merge / conflicto**: por **similitud de embeddings** (en claro) + descifrado in-process de los candidatos cercanos para comparación textual fina. Nunca por comparación de blobs cifrados.
- Esto es ingeniería no trivial (es justo lo que ADR-003 quería comprar), pero es la única opción que preserva el moat. La disciplina obligatoria: que el engine viva **detrás del Protocol**, no acoplado al storage, para no degenerar en monolito.

### D5 — Roadmap graph/temporal (estilo Graphiti) como **v3 explícito, NO M7**

- El SOTA 2026 en memoria temporal es el **knowledge graph bi-temporal** (Zep/Graphiti: `valid-time` — cuándo el hecho fue cierto — + `transaction-time` — cuándo lo aprendimos —, con invalidación de hechos por *validity windows*). Es el approach correcto para hechos que cambian ("cambié de trabajo", "me mudé").
- **Se adopta como DISEÑO de referencia, no como dependencia.** Razones del diferimiento, en orden de peso:
  1. **Costo/latencia prohibitivos hoy para el caso de uso**: el approach graph (Graphiti/Zep) reporta footprint de cómputo por conversación **un orden de magnitud mayor** que el vectorial, y un *retrieval post-ingestion* que frecuentemente falla hasta que el procesamiento background del grafo termina (minutos/horas después). Para un asistente personal **real-time on-prem con una sola RTX 4080 compartida** (Gemma + Qwen ya conviven ahí, ADR-009), eso es casi descalificante en el MVP.
  2. Exige Neo4j/FalkorDB/Kuzu, que viola el espíritu "un solo store" de ADR-004.
  3. Asume plaintext en sus nodos (mismo problema estructural que Mem0).
- **Implementación v3 (tablas/conceptos nuevos, todos con gate sagrado regla #3)**:
  - Columnas bi-temporales en `semantic_memory`: `valid_from` / `valid_until` (validez del hecho en el mundo) además de los `created_at`/`updated_at` existentes (cuándo lo registramos).
  - Tabla `memory_relations` (aristas entre entidades, con sus propios intervalos de validez).
  - Tabla `memory_entities` (personas, organizaciones, lugares), extraídas on-prem con GLiNER/spaCy (sin LLM externo). **DECISIÓN DE PRIVACIDAD DE PRIMER ORDEN, a revisar explícitamente en v3, no detalle de implementación**: una lista de entidades vinculadas a un usuario (nombre del terapeuta, diagnósticos, vínculos) **es** contenido íntimo — exponerla sin cifrar para habilitar graph-lite/filtrado SQL erosiona el moat justo en el modo Bienestar, que es donde más importa. v3 debe decidir conscientemente si estas entidades van cifradas (perdiendo el filtrado SQL directo) o si solo un subconjunto no-sensible queda en claro.
  - Si v3 necesita razonamiento multi-hop real sobre el grafo, evaluar **Apache AGE** (extensión Postgres nativa para grafos) **antes** que Neo4j, para mantener el stack en un solo motor.
- **v3 no se promete para M7 ni M8.** Es horizonte. M7/M8 viven perfectamente sin grafo.

### D6 — Threat model de privacidad (el moat, documentado explícito)

- **Master key SERVER-SIDE** (`MEMORY_ENCRYPTION_MASTER_KEY`, env var), key derivada **por usuario** vía HKDF-SHA256, AES-256-GCM, nonce aleatorio de 96 bits por record (`crypto.py:95-120`).
- **Qué protege**: leak/dump/backup robado/SQL-injection de la DB. Sin el master key + el `user_id`, `content`/`summary` no son legibles. Blast radius acotado: comprometer la key derivada de un usuario no descifra a los demás.
- **Qué NO protege**:
  - Un **server comprometido**. El master key vive en el proceso; un atacante con ejecución de código en el server *puede* descifrar. Esto es **aceptado por diseño** y es lo que **habilita** toda la inteligencia in-process (embed/extract/dedup/rerank sobre plaintext en RAM). El plaintext existe efímeramente en memoria durante write y durante el rerank de top-K; nunca se persiste en claro.
  - **Fuga parcial vía embeddings en claro (riesgo nombrado, no oculto)**: los `Vector(1024)` NO están cifrados (se necesitan para la búsqueda). Un atacante con la DB pero **sin** el master key puede correr **embedding-inversion attacks** para recuperar *aproximaciones* del texto desde el vector. El cifrado protege `content` literal, pero el embedding filtra **señal semántica** recuperable. Esto **no** cambia la decisión (sin embeddings en claro no hay búsqueda vectorial), pero un ADR honesto en privacidad debe declararlo: el moat es fuerte sobre el contenido literal, parcial sobre la señal semántica. Mitigación futura a evaluar: cifrado de embeddings con esquemas que preserven distancia (caros) o aceptar el riesgo como parte del threat model declarado.
- **Posicionamiento Apple-vs-Google**: el moat es ofrecer "tu memoria íntima cifrada en infra que vos controlás", algo que los gigantes cloud no pueden dar fácil. El cifrado **no se negocia; se potencia**. Tope de gama *dentro* de la restricción privacy-first — sin sobre-vender: es defensa fuerte contra leak de DB, no E2EE.

## Scope: qué es M7, qué es M8, qué es v3 (honesto, sin inflar)

**M7 — AHORA (foundation, rerank-ready, sin inteligencia real):**
- Implementar los wrappers `semantic.py` / `episodic.py` / `procedural.py` sobre el storage propio: `add`/`search`/`update`/`delete` que cifran con `crypto.py` al escribir y descifran al leer.
- `search` = ANN sobre pgvector HNSW (vía `EmbeddingClient`, hoy `FakeEmbeddingClient`) → descifrar top-K in-process. **Sin** rerank real todavía, pero **con el `Reranker` Protocol + `FakeReranker` cableados** en el pipeline (el slot existe, la implementación es un passthrough determinista).
- Tests de integración contra Postgres real: round-trip cifrado, dimensión 1024, que `content` quede `BYTEA` cifrado en la fila, aislamiento por `user_id`.
- **NO** se implementa: extracción LLM, dedup, consolidación, rerank real, sharding, pgvectorscale, blind-index, graph.

**M8 — DESPUÉS (inteligencia + consolidación):**
- Cablear el `EmbeddingClient` real (decidir bge-m3 vs migración a Qwen3-Embedding-0.6B **con A/B real**; si se migra, re-embed del corpus).
- Cablear el `Reranker` real (Qwen3-Reranker-0.6B / bge-reranker-v2-m3).
- `MemoryEngine` in-house: extracción `ADD/UPDATE/DELETE/NOOP` con Qwen, dedup por embedding + descifrado in-process, consolidación post-turn vía Celery (roadmap §5.1).
- Remover `mem0ai` de `pyproject.toml` (o aislarlo como extractor).
- *(opcional)* contextual retrieval en el write path.

**v3 — HORIZONTE (graph/temporal):**
- Columnas bi-temporales, `memory_entities` (con la decisión de privacidad de D5 resuelta), `memory_relations`, entity linking on-prem, eventual Apache AGE. Todo con gate sagrado regla #3. No comprometido a fecha.

## Consecuencias positivas

- **El moat queda intacto y potenciado**: cifrado a nivel campo + tablas sagradas + master key server-side, sin acoplar la privacidad al roadmap de ningún tercero.
- **Coherencia arquitectónica**: la memoria se construye con el mismo patrón Protocol + Fake que la capa LLM ya probó (inyectable, testeable sin red/GPU/DB real).
- **ADR-004, 007, 008, 009 quedan vigentes y reforzados** — esta no es una reescritura, es cerrar la única contradicción abierta (ADR-003).
- **Camino de escalado claro y barato** (HNSW → particionado por user_id → pgvectorscale) sin salir de Postgres.
- **Pipeline el mejor posible bajo cifrado**: vector-first + decrypt-top-K + cross-encoder rerank es el techo de calidad **compatible con cifrado at-rest**. No iguala a un híbrido con BM25 (que el cifrado nos veda): el costo asumido es el exact-match léxico, mitigado por el rerank.
- **Costo del decrypt-top-K ya optimizado (SCAL-02, MITIGADO post-M7, no diferido)**: el "descifrar el top-K in-process" de D2 (paso 3 del read path) no es un cuello de botella pendiente. La key derivada por usuario se cachea (`_derive_key_cached`, LRU por `(master_key, user_id)` en `app/core/crypto.py`): HKDF-SHA256 ya no se re-corre por record. `decrypt_many_for_user` deriva la key UNA vez y reusa una única instancia `AESGCM` para todo el lote del top-K (y de los listados/export), y el descifrado se offloadea a un thread (`asyncio.to_thread`, `app/memory/semantic.py:114` / `episodic.py:108`): es CPU-bound y OpenSSL libera el GIL, así que no bloquea el event loop bajo concurrencia. El antiguo costo de re-derivar HKDF + reconstruir `AESGCM` por record en el top-K ya no existe.

## Consecuencias negativas

- **Hay que escribir la inteligencia a mano** (extracción, dedup, conflicto): es justo lo que ADR-003 quería comprar. El costo de mantener el prompt de extracción y la heurística de merge recae en el equipo.
- **Riesgo de reinventar peor** lo que Mem0/Zep optimizaron en benchmarks (LongMemEval). Mitigable usándolos como referencia de algoritmo.
- **El cifrado no bloquea la inteligencia, la empuja in-process**: dedup/merge/rerank sobre plaintext descifrado en RAM, con la superficie de exposición efímera que eso implica (aceptada por el threat model).
- **Eventual migración de embeddings** (bge-m3 → Qwen3-0.6B) es re-embed del corpus completo, aunque sin tocar schema, y solo si la A/B la justifica.
- **Sin keyword search server-side** sobre el contenido (costo asumido del cifrado). Mitigación: rerank; blind-index queda como opción futura.
- **Fuga semántica parcial vía embeddings en claro** (embedding-inversion): aceptada y documentada en D6.

## Mitigaciones

- **Protocols + Fakes deterministas** (`Reranker`, `MemoryEngine`) desde M7: el pipeline se prueba end-to-end sin modelos reales, igual que la capa LLM.
- **Mem0 como referencia, no dependencia**: si se mantiene `mem0ai`, aislarlo tras un adapter que solo use el extractor; nunca su store ni su SQLite.
- **Escalado por medición**: no migrar a pgvectorscale ni a sharding hasta que el profiling (build **y** query) lo justifique.
- **Migración de embeddings gateada por A/B real** sobre corpus de Ynara, no por benchmark agregado ni por fecha.
- **Tests de regresión sobre el storage cifrado** (round-trip, dimensión, `content` cifrado en fila, aislamiento por user) en M7, ampliados con dedup/consolidación en M8.

## Alternativas descartadas

- **Mem0 OSS como engine de storage (status quo ADR-003)**: incompatible con el cifrado ya aprobado (ADR-007 D3). Fijaría su DDL en plaintext, necesita plaintext persistido para dedup/extract, mantiene SQLite de historia en claro, sin hook pre-store. Persistir cifrado bajo Mem0 = forkear su core (peor que in-house) o renunciar al cifrado (matar el moat). **Es lo que este ADR supersede.**
- **Graphiti (Apache-2.0) adaptado a storage cifrado**: es el SOTA real en temporal/graph, pero (a) costo/latencia prohibitivos para real-time on-prem en una GPU compartida, (b) exige Neo4j/FalkorDB/Kuzu (viola "un solo store" de ADR-004), (c) no persiste cifrado (mismo problema estructural que Mem0). Se adopta su **diseño** (bi-temporal) en v3, no su runtime.
- **Letta / MemGPT**: controla el DDL de sus tablas (`archival_passages`), contenido en texto plano, sin hook de cifrado. Lock-in al runtime de Letta (storage e infra inseparables).
- **LangMem (LangChain)**: el más compatible en teoría (storage-agnostic vía `BaseStore`), pero p95 de búsqueda reportado en el orden de decenas de segundos lo descalifica para retrieval real-time, y vale poco fuera de LangGraph.
- **Vector DB dedicada (Qdrant / Milvus / Weaviate / LanceDB)**: rompe ACID con el relacional, exige outbox/saga para consistencia, duplica ops/backups, y **ninguna** cifra a nivel campo nativo — el trade-off de cifrado vs búsqueda por texto es idéntico al de Postgres pero sin ACID gratis. Turbopuffer además es cloud-only (viola regla #4). Reservado para un escenario lejano de escala medida, no temida.
- **Renunciar al cifrado at-rest para habilitar engine + BM25 + dedup textual**: desbloquearía todo el ecosistema, pero **mata el moat**. ADR-007 ya descartó disk-level-only explícitamente. Se documenta solo para descartarlo con argumento.
- **Cambiar `Vector(1024)` a 2048**: duplica storage/compute sin ganancia proporcional de recall, y sería re-migración sagrada. No.

## Impacto en archivos del repo

### `docs/architecture/adrs/ADR-003-mem0-vs-letta.md`
Marcar **Estado: Superseded por ADR-010** (engine de storage de la capa semántica). Honestidad: ADR-003 ya contemplaba *custom hooks* propios para episódica y procedural — **solo se reemplaza la premisa de Mem0 como engine de STORAGE de la capa semántica**; el espíritu de "hooks propios" para episódica/procedural se mantiene y se generaliza ahora a las tres capas.

### `docs/product/MEMORY.md`
Corregir la sección "Semántica": hoy dice *"registros de Mem0 OSS v2 en `semantic_memory`"*. Reemplazar por: storage propio sobre `semantic_memory` (cifrado AES-256-GCM, embedding 1024-dim en pgvector), engine in-house. Actualizar el puntero de engine de ADR-003 a ADR-010.

### `docs/planning/BACKEND-MEMORY-ROADMAP.md`
§5.1 (consolidación post-turn) asume "formato Mem0 ADD/UPDATE/DELETE/NOOP" — aclarar que el **patrón** ADD/UPDATE/DELETE/NOOP se mantiene como contrato del extractor in-house (Qwen), no como dependencia de Mem0. Actualizar el link de ADR-003 a ADR-010.

### `apps/backend/pyproject.toml`
`mem0ai>=0.1.0`: remover en M8 (o aislar tras adapter de solo-extracción). **No** en el PR de este ADR.

### `apps/backend/app/memory/{semantic,episodic,procedural}.py`
Hoy stubs `NotImplementedError`. El docstring de `semantic.py` dice *"Wrapper sobre Mem0 OSS v2"* — reescribir a "storage propio cifrado". Implementación real del storage en M7; engine en M8. *(Nota post-aprobación: M7 completado; stubs reemplazados por implementación real con storage cifrado propio; docstrings actualizados.)*

### Nuevo: `Reranker` Protocol + `FakeReranker`
Espejando `EmbeddingClient` (`embedding.py`), `runtime_checkable`. En M7 (contrato + Fake passthrough). El `MemoryEngine` Protocol (extract/consolidate/search) en M8.

### `ynara.config.json`
Sin cambios en M7. En M8, si se aprueba la migración del embedder, `[memory].embedding_model` y se agrega `[memory].reranker_model` (gate humano por regla #1).

### Schema sagrado (solo v3, gate regla #3)
`semantic_memory.valid_from`/`valid_until`, tablas `memory_entities` / `memory_relations`. **No** en M7/M8.

## Links

- [`ADR-003`](./ADR-003-mem0-vs-letta.md) — Mem0 OSS v2 como engine (**superseded por este ADR**).
- [`ADR-004`](./ADR-004-postgres-pgvector-vs-pinecone.md) — Postgres + pgvector como único store (vigente, reforzado: pgvectorscale como escalado).
- [`ADR-007`](./ADR-007-memory-decay-retention-encryption.md) — decay, retention, cifrado a nivel campo (vigente, base de este ADR).
- [`ADR-008`](./ADR-008-embedding-model-bge-m3.md) — bge-m3 1024-dim (vigente; Qwen3-Embedding-0.6B como candidato a validar con A/B en M8).
- [`ADR-009`](./ADR-009-vllm-serving-topology-tool-parsers.md) — topología vLLM (relevante para servir embedder + reranker on-prem).
- [`docs/product/MEMORY.md`](../../product/MEMORY.md) — modelo de memoria (a corregir: "registros de Mem0").
- [`docs/planning/BACKEND-MEMORY-ROADMAP.md`](../../planning/BACKEND-MEMORY-ROADMAP.md) — roadmap (§5.1 consolidación, a actualizar).
- `apps/backend/app/core/crypto.py` — `encrypt_for_user` / `decrypt_for_user` (la base in-process de todo el pipeline).
- `apps/backend/app/llm/clients/embedding.py` — `EmbeddingClient` Protocol + `FakeEmbeddingClient` (patrón a espejar con `Reranker`).
- Familia de modelos on-prem candidatos: `Qwen/Qwen3-Embedding-0.6B`, `Qwen/Qwen3-Reranker-0.6B`, `BAAI/bge-m3`, `BAAI/bge-reranker-v2-m3` (Apache 2.0).
