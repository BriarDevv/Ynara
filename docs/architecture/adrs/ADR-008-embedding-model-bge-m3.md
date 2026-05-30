# ADR-008: Modelo de embedding — BAAI bge-m3 (1024-dim, on-prem)

## Estado
Aceptado

## Fecha
2026-05-30

> Aprobado por Mateo García (operador humano) el 2026-05-30. Formaliza una
> decisión que ya estaba implícita en ADR-004, ADR-007 y la migración inicial
> (`vector(1024)`), para **desbloquear PR C** (crypto + wrappers de memoria).

## Contexto

La memoria semántica de Ynara busca por similitud sobre embeddings (ADR-004:
Postgres + pgvector, índices HNSW). Falta fijar **qué modelo** genera esos
embeddings. Restricciones del producto:

- **On-prem obligatorio** (regla #4 de `AGENTS.md`): el texto del usuario NUNCA
  sale del perímetro. Embeddear es procesar contenido del usuario, así que un
  API de embeddings externo (OpenAI, Cohere, Voyage) queda descartado de entrada.
- **Multilingüe con español primero**: la UX es rioplatense; el modelo tiene
  que rankear bien en español, no solo en inglés.
- **Dimensión ya comprometida**: la migración inicial y los modelos SQLAlchemy
  usan `vector(1024)` (`EMBEDDING_DIM = 1024`); ADR-007 cifra `content`/`summary`
  pero deja los embeddings en plano para la búsqueda. El modelo elegido debe
  producir **1024 dims** o se re-migra una tabla sagrada (caro, regla #3).
- **Contexto largo**: los `summary` de memoria episódica pueden ser párrafos;
  conviene tolerar entradas largas sin truncar agresivo.
- **Servible junto al stack on-prem**: sin sumar un runtime exótico (vLLM ya
  sirve los LLMs, ADR-009).

`ynara.config.json[memory].embedding_model` ya dice `bge-m3` y Mem0 (ADR-003)
lo toma como engine de embeddings; este ADR cierra la decisión formalmente.

## Decisión

**`BAAI/bge-m3`** como modelo de embedding de memoria, servido **on-prem**,
usando su salida **densa de 1024 dimensiones**.

- **Dense retrieval** de 1024 dims → entra directo en `vector(1024)` + HNSW con
  `vector_cosine_ops` (ya en la migración). Vectores normalizados, distancia
  **cosine**.
- **Multilingüe**: bge-m3 ("M3" = Multi-Linguality, Multi-Functionality,
  Multi-Granularity) cubre 100+ idiomas con buen desempeño en español.
- **Contexto hasta 8192 tokens**: cubre `summary`/`content` largos sin chunking
  agresivo en el MVP.
- **Pesos abiertos**: se descarga y corre on-prem (sentence-transformers /
  FlagEmbedding en MVP; un server liviano tipo TEI/Infinity en V2). Sin licencia
  que ate a un SaaS.
- **Solo el modo denso en el MVP**: bge-m3 también da sparse y multi-vector
  (ColBERT). Los dejamos fuera del MVP (pgvector indexa el denso); quedan como
  palanca futura para hybrid search **sin cambiar de modelo**.

`EMBEDDING_MODEL=bge-m3` (`.env`) + `ynara.config.json[memory].embedding_model`
son la fuente de verdad; el código de embeddings (PR C / Mem0) lo lee de ahí.

## Consecuencias positivas

- **Cero texto de usuario a terceros** (regla #4): el embedding se calcula
  on-prem, igual que la inferencia.
- **Sin re-migración**: 1024 dims calza con el schema sagrado ya creado; no se
  toca una tabla sagrada (regla #3).
- **Español de primera**: rankea bien en la lengua de la UX.
- **Una sola familia para crecer**: si más adelante hace falta hybrid (denso +
  sparse) o re-ranking multi-vector, es el MISMO modelo — no hay que re-embeddear
  todo con otro.
- **Desbloquea PR C**: con la dimensión y el modelo fijos, el crypto + los
  wrappers de memoria pueden avanzar.

## Consecuencias negativas

- **Costo de cómputo on-prem**: embeddear consume GPU/CPU local. bge-m3 es más
  pesado que un MiniLM; para el volumen MVP (pocos embeddings por turno) es
  despreciable, pero a escala hay que dimensionar el server de embeddings.
- **1024 dims = más storage por vector** (~4KB en `vector(1024)`) que un modelo
  de 384/768 dims. Aceptable para el rango de escala (ADR-004); HNSW lo absorbe.
- **Sin re-ranking en el MVP**: solo denso. Si el recall no alcanza, se activa
  el sparse/multi-vector de bge-m3 (palanca ya disponible en el mismo modelo).

## Mitigaciones

- **`EMBEDDING_MODEL` configurable** (`.env` + `ynara.config.json`): si bge-m3
  resulta caro o aparece algo mejor a 1024 dims (p.ej. `multilingual-e5-large`),
  se cambia sin re-migrar — pero **hay que re-embeddear** todo el corpus (los
  vectores viejos no son comparables con los nuevos). Es migración de DATOS, no
  de schema; documentarla como tal.
- **Servir el embedding aparte del LLM**: en V2, un server dedicado
  (TEI/Infinity) desacopla el throughput de embeddings del de generación.
- **Test de dimensión**: cuando se cablee el embedder (PR C), un test que afirme
  que el vector producido tiene largo 1024 (alinea modelo ↔ schema).

## Alternativas descartadas

- **APIs de embedding externas** (OpenAI `text-embedding-3`, Cohere, Voyage):
  violan regla #4 — embeddear es mandar texto del usuario a un tercero.
- **`multilingual-e5-large`** (1024-dim, multilingüe): alternativa válida y
  compatible con el schema; bge-m3 gana por contexto más largo (8192 vs 512) y
  por traer sparse/multi-vector en el mismo modelo. Queda como **plan B drop-in**
  si bge-m3 decepciona (mismo 1024-dim → re-embeddear, sin re-migrar).
- **`nomic-embed-text` / MiniLM (384-768 dim)**: más liviano y barato, pero
  sesgo al inglés y dimensión distinta → re-migración de tabla sagrada. No.
- **bge-m3 sparse/multi-vector en el MVP**: más recall potencial, pero pgvector
  indexa el denso; sumar sparse ahora es complejidad sin necesidad probada. Se
  deja como palanca, no como decisión inicial.

## Links

- [`ADR-003`](./ADR-003-mem0-vs-letta.md) — Mem0 OSS v2 como engine de memoria.
- [`ADR-004`](./ADR-004-postgres-pgvector-vs-pinecone.md) — Postgres + pgvector (1024-dim).
- [`ADR-007`](./ADR-007-memory-decay-retention-encryption.md) — embeddings en plano; `content`/`summary` cifrados.
- [`docs/product/MEMORY.md`](../../product/MEMORY.md) — modelo de memoria.
- `ynara.config.json[memory].embedding_model` + `EMBEDDING_MODEL` (`.env`).
