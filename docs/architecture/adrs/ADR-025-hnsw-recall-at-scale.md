# ADR-025: Recall de HNSW a escala — índice global con post-filtro `user_id` y `ef_search` sin tunear (MEM-SACRED-02, diferido)

## Estado
Propuesto (diferido — sin migración hoy, latente)

## Fecha
2026-06-25

## Contexto

La búsqueda ANN de las capas de memoria sagradas (`semantic_memory`,
`episodic_memory`) corre sobre un **único índice HNSW global por tabla**, con
filtro por `user_id` aplicado como predicado del query (post-filtro), no como
partición física del índice. Verificado contra el código:

- [`app/models/memory.py`](../../../apps/backend/app/models/memory.py) define un
  HNSW **global** por tabla:
  `ix_semantic_memory_content_embedding_hnsw` sobre `content_embedding`
  (`vector_cosine_ops`, líneas ~64-69) e
  `ix_episodic_memory_summary_embedding_hnsw` sobre `summary_embedding`
  (líneas ~113-118). Ninguno se declara con `m` / `ef_construction` explícitos
  ni se particiona por tenant — son índices únicos sobre toda la tabla,
  cross-user.
- [`app/memory/semantic.py`](../../../apps/backend/app/memory/semantic.py) (~99-104)
  arma el query como
  `WHERE user_id == self._user_id` + `ORDER BY content_embedding.cosine_distance(qvec)`
  + `LIMIT _ANN_TOP_K` (50). Idéntico en
  [`app/memory/episodic.py`](../../../apps/backend/app/memory/episodic.py) (~92-97)
  sobre `summary_embedding`.
- **`ef_search` no se setea por sesión**: no hay `SET LOCAL hnsw.ef_search` en el
  camino de lectura; el query usa el `ef_search` default de pgvector.

A escala, esto tiene una trampa conocida de pgvector: un HNSW global **recorre
el grafo global** y recién después aplica el filtro `user_id`. Con `ef_search`
fijo, los candidatos que el grafo devuelve antes de filtrar pueden ser en su
mayoría de **otros** usuarios, y el post-filtro los descarta — degradando el
**recall@k efectivo por usuario** (se piden K vecinos del usuario X pero el
grafo entrega K vecinos globales, mayormente de otros, y quedan menos de K
propios). Para un corpus chico (MVP) esto no se nota; a `>>100k` usuarios con
vecindarios densos sí puede.

ADR-010 D1 ya anticipó el camino de escalado (sharding `LIST PARTITION` por
`user_id`, cada partición con su HNSW; `pgvectorscale`/StreamingDiskANN como
upgrade in-place) y fijó la **regla práctica**: *no salir de Postgres ni tocar
el índice hasta que el query vectorial sea el bottleneck medido, no temido*.
Este ADR **documenta y difiere** la deuda de recall a escala (MEM-SACRED-02)
bajo esa misma disciplina: deja constancia del tradeoff, el umbral de
re-evaluación y el plan, sin tocar el schema sagrado hoy.

> **Nota de gate sagrado (regla #3 de [`AGENTS.md`](../../../AGENTS.md)):**
> cualquier cambio efectivo de estos índices (declarar `m`/`ef_construction`,
> particionar, cambiar a IVFFlat) toca `app/models/memory.py` + una migración
> Alembic sobre tablas sagradas → 1 aprobación humana explícita en el PR. Por eso
> este ADR queda **Propuesto/diferido**, no Aceptado: no autoriza la migración,
> la encuadra.

## Decisión

**Se mantiene el HNSW global con post-filtro `user_id` y `ef_search` default
mientras el recall@k por usuario no sea un bottleneck medido. La deuda de recall
a escala (MEM-SACRED-02) queda documentada y diferida; no hay migración hoy.**

El estado actual es **deliberadamente latente**: para el corpus MVP el recall
por usuario es correcto (pocos vecinos por usuario, el post-filtro casi no
descarta), y el costo de tunear/particionar prematuramente (gate sagrado +
re-build de índices + complejidad operativa) no se justifica sin medición.

## Umbral de re-evaluación

Re-evaluar (correr el benchmark de abajo y, si confirma, ejecutar el plan)
cuando se cumpla **cualquiera** de estas condiciones, medidas en producción:

1. **Escala de tenants**: del orden de `>>100k` usuarios con corpus por usuario
   denso (muchos vectores cercanos cross-user que el grafo global mezcla).
2. **Degradación de recall@k por usuario medida**: un benchmark muestra que el
   ANN devuelve menos de K vecinos propios reales (el post-filtro `user_id`
   descarta una fracción creciente del top-K global) respecto del recall exacto
   (brute-force) sobre el mismo usuario.
3. **Presión de RAM en el build/insert del HNSW global** (ADR-010 D1 ya marca el
   build incremental como bottleneck a vigilar antes que la latencia de query).

## Plan (cuando el umbral se cruce)

1. **Benchmark de `recall@k` sintético**: generar un corpus multi-tenant
   representativo (muchos usuarios, densidad realista) y medir `recall@k` por
   usuario del ANN actual (HNSW global + post-filtro) **contra** el ground-truth
   exacto (brute-force cosine sobre las filas de ese usuario). Esto cuantifica la
   degradación real antes de tocar nada (regla "medido, no temido" de ADR-010).
2. Si el benchmark confirma degradación, evaluar en este orden (de menos a más
   invasivo sobre el schema sagrado):
   - **`SET LOCAL hnsw.ef_search` por sesión**: subir `ef_search` en el camino
     de lectura agranda la lista de candidatos del grafo antes del post-filtro,
     recuperando recall por usuario a costa de latencia. Es el cambio **menos
     invasivo** (no toca el índice, solo el query path) y el primero a probar.
   - **Declarar `m` / `ef_construction` explícitos** en los índices HNSW (hoy
     defaults): un grafo mejor construido mejora el recall base. Es un re-build
     de índice → gate sagrado.
   - **HNSW parcial / particionado por tenant** (`LIST PARTITION` por `user_id`,
     cada partición con su propio HNSW — el camino de ADR-010 D1): el planner
     hace pruning por `user_id` y el grafo de cada partición es **solo** del
     usuario, así que el post-filtro deja de descartar candidatos ajenos. Es la
     solución estructural al problema de recall por tenant.
   - **IVFFlat como alternativa**: si el perfil de carga favorece listas
     invertidas sobre el grafo HNSW (corpus muy grande, tolerancia a recall algo
     menor a cambio de menor RAM de build), evaluarlo como índice alternativo.
3. Cualquiera de los dos últimos (re-build / partición / IVFFlat) entra como
   migración Alembic sobre tablas sagradas, con **1 aprobación humana explícita**
   (regla #3). El primero (`ef_search` por sesión) es código del read path, no
   schema.

## Consecuencias positivas

- **Cero costo hoy**: el HNSW global con post-filtro es correcto para el corpus
  MVP; no se paga complejidad ni gate sagrado antes de necesitarlo.
- **Deuda nombrada y con plan**: MEM-SACRED-02 queda documentada con umbral
  explícito y secuencia de mitigación ordenada de menor a mayor invasividad, así
  el día que escale no se improvisa.
- **Coherencia con ADR-010 D1**: el plan (partición por `user_id`, `pgvectorscale`
  como upgrade in-place) es exactamente el camino de escalado ya decidido; este
  ADR solo le agrega el ángulo de **recall** (no solo latencia/RAM).

## Consecuencias negativas

- **Riesgo latente**: si el producto escala más rápido de lo previsto y nadie
  corre el benchmark, el recall por usuario puede degradarse en silencio (no hay
  alerta automática hoy).
- **`ef_search` default es opaco**: el comportamiento de recall depende de un
  valor que no está versionado en el repo (es el default de pgvector vigente).

## Mitigaciones

- El **benchmark de recall@k sintético** del plan es la red de seguridad: corre
  antes de tocar nada y cuantifica la degradación, evitando tanto el under-tuning
  (recall malo en silencio) como el over-engineering (particionar sin necesidad).
- ADR-010 D1 ya dejó el camino de escalado barato (partición → pgvectorscale) sin
  salir de Postgres, así que la mitigación estructural no exige cambio de stack.

## Alternativas descartadas (para HOY)

- **Particionar / tunear `m`/`ef_construction` ahora.** Over-engineering para el
  corpus MVP: gate sagrado + re-build sin un bottleneck medido. Contradice la
  regla "medido, no temido" de ADR-010 D1. Diferido al umbral.
- **Setear `ef_search` alto globalmente "por las dudas".** Sube la latencia de
  todas las búsquedas sin evidencia de que el recall esté degradado; el lugar
  correcto es `SET LOCAL` por sesión cuando el benchmark lo justifique, no un
  default agresivo a ciegas.
- **Cifrar/indexar distinto para evitar el post-filtro.** Fuera de alcance: el
  filtro `user_id` es aislamiento estructural (regla #3); el problema no es el
  filtro sino el orden grafo-global-luego-filtro, que se resuelve con partición o
  `ef_search`, no quitando el filtro.

## Links

- [`apps/backend/app/models/memory.py`](../../../apps/backend/app/models/memory.py) —
  índices HNSW globales (`ix_semantic_memory_content_embedding_hnsw`,
  `ix_episodic_memory_summary_embedding_hnsw`).
- [`apps/backend/app/memory/semantic.py`](../../../apps/backend/app/memory/semantic.py) —
  query ANN con post-filtro `user_id` (`search`).
- [`apps/backend/app/memory/episodic.py`](../../../apps/backend/app/memory/episodic.py) —
  ídem sobre `summary_embedding`.
- [`ADR-004`](./ADR-004-postgres-pgvector-vs-pinecone.md) — Postgres + pgvector
  como único store.
- [`ADR-010`](./ADR-010-memory-architecture-v2.md) — arquitectura de memoria v2;
  D1 fija el camino de escalado (partición por `user_id`, pgvectorscale) y la
  regla "medido, no temido".
