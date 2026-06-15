# GLOSSARY.md — Vocabulario de Ynara

Términos que aparecen recurrentemente en el repo y en conversaciones
del equipo. Si encontrás un término ambiguo y no está acá, agregalo
con un PR.

## Producto

- **Modo** — uno de los 5 perfiles operativos del producto:
  productividad, estudio, bienestar, vida, memoria. Definidos en
  `ynara.config.json`.
- **Hand-off** — cuando Ynara cambia de modo (manual o sugerido) en
  medio de una conversación.
- **Sesión** — span continuo de interacción de un usuario, marcado
  por inactividad > N minutos o cambio explícito.

## Memoria

- **Capa semántica** — hechos persistentes sobre el usuario.
  Embeddings en pgvector; implementación in-house (ADR-010).
- **Capa episódica** — resúmenes de conversaciones pasadas.
- **Capa procedural** — preferencias y patrones (JSONB).
- **Consolidación** — proceso async (Celery) que extrae memoria
  nueva, deduplica y persiste.
- **Recall** — operación de búsqueda en memoria.
- **Tabla sagrada** — `semantic_memory`, `episodic_memory`,
  `procedural_memory`. Requieren tests + 1 aprobación humana
  explícita para cualquier migración (regla #3).

## Modelos

- **Gemma** — Gemma 4 12B. Modelo conversacional. Solo lee
  memoria.
- **Qwen** — Qwen 3.5 9B. Modelo agente. Lee y escribe memoria,
  llama tools.
- **bge-m3** — modelo de embeddings, 1024 dimensiones.
- **Reranker** — reordena los candidatos del ANN (el top-K que devuelve
  pgvector) por relevancia antes del recall final. Contrato `Reranker`
  (Protocol) en `apps/backend/app/llm/clients/reranker.py`, con
  `FakeReranker` passthrough determinista para dev/test y `VllmReranker`
  real contra la API `/rerank` de vLLM (cross-encoder). Ollama no sirve
  cross-encoders, así que en dev se usa el Fake.
- **vLLM** — motor de serving reservado para GPU de 24 GB+ (ADR-014).
  `LLM_BACKEND=vllm` es el nombre legacy del cliente HTTP, no implica que
  vLLM sea el motor local. En dev se usan Fakes
  (FakeLlmClient/FakeEmbeddingClient/FakeReranker).
- **Ollama** — motor de serving local en 16 GB (RTX 4080 Super), elegido
  en ADR-014: es el único que sostiene el dual-stack completo
  (Gemma 12B + Qwen 9B + bge-m3 co-residentes).

## Stack

- **Router LLM** — `apps/backend/app/llm/router.py`. Decide modelo
  según modo activo.
- **Tool** — función que el agente Qwen puede invocar (calendar,
  reminder, memory, etc.). Definidas en
  `apps/backend/docs/TOOLS.md`.
- **Tabla operativa** — cualquier tabla que no sea de memoria
  sagrada (users, sessions, audit_log, etc.).

## Auth

- **`sid`** — claim (UUID hex) que identifica la familia/sesión de un
  token. Agrupa el access + todos los refresh rotados de esa sesión bajo
  una unidad revocable. Lo llevan tanto el access como el refresh (#142).
- **Familia de sesión** — conjunto de tokens que comparten el mismo `sid`.
  Se revocan de golpe con `revoke_family` (un logout o un breach matan la
  familia entera, no un solo `jti`).
- **Reuse-detection** — mecanismo de `/v1/auth/refresh`: un refresh ya
  rotado que reaparece se evalúa contra el grace. Dentro del grace
  (`AUTH_REFRESH_REUSE_GRACE_SECONDS`) es un retry benigno e idempotente;
  fuera del grace es un breach → revoca la familia entera → 401 (#142).
- **Grace marker** — flag Redis efímero que marca un refresh recién rotado
  y apunta al `jti` del sucesor. Habilita la idempotencia del retry dentro
  de la ventana `AUTH_REFRESH_REUSE_GRACE_SECONDS` (#142).

## Infra

- **Fase MVP** — etapa actual. DB sobre Supabase como Postgres
  gestionado.
- **Fase V2** — etapa post-validación. DB Postgres self-hosted,
  toda la stack on-prem.
- **Cutover** — momento de la migración Supabase → self-hosted.
- **R2** — Cloudflare R2, storage de objetos.
- **Cloudflare Tunnel** — túnel desde la VPS al edge de Cloudflare,
  evita exponer puertos.

## Equipo

- **CODEOWNER** — persona del equipo responsable de aprobar PRs que
  tocan ciertos paths. Definidos en `.github/CODEOWNERS`.
- **Tabla sagrada review** — review humano explícito (1 aprobación
  formal en el PR, además del operador autor) + tests pasando,
  requerido para migraciones que tocan capas de memoria.

## IA / agentes

- **AGENTS.md** — contrato de comportamiento para IAs que trabajan
  sobre el repo.
- **Adapter** — archivo `.md` o carpeta específica de una
  herramienta de IA (Claude, Codex, Gemini). Solo punteros, no
  contenido propio.
- **Sub-agent** — agente especializado dentro de una sesión (planner,
  executor, verifier, etc.).
- **ADR** — Architecture Decision Record. Documento corto en
  `docs/architecture/adrs/` que captura una decisión técnica.
