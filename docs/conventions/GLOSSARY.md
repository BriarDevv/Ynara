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
  Embeddings + Mem0.
- **Capa episódica** — resúmenes de conversaciones pasadas.
- **Capa procedural** — preferencias y patrones (JSONB).
- **Consolidación** — proceso async (Celery) que extrae memoria
  nueva, deduplica y persiste.
- **Recall** — operación de búsqueda en memoria.
- **Tabla sagrada** — `semantic_memory`, `episodic_memory`,
  `procedural_memory`. Requieren tests + 2 aprobaciones para
  cualquier migración.

## Modelos

- **Gemma** — Gemma 4 26B-A4B. Modelo conversacional. Solo lee
  memoria.
- **Qwen** — Qwen 3.5 9B. Modelo agente. Lee y escribe memoria,
  llama tools.
- **bge-m3** — modelo de embeddings, 1024 dimensiones.
- **vLLM** — servidor de inferencia que usamos en producción.
- **Ollama** — servidor de inferencia alternativo para dev local.

## Stack

- **Router LLM** — `apps/backend/app/llm/router.py`. Decide modelo
  según modo activo.
- **Tool** — función que el agente Qwen puede invocar (calendar,
  reminders, memory, etc.). Definidas en
  `apps/backend/docs/TOOLS.md`.
- **Tabla operativa** — cualquier tabla que no sea de memoria
  sagrada (users, sessions, audit_log, etc.).

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
- **Tabla sagrada review** — review humano + 2 aprobaciones
  requeridas para migraciones que tocan capas de memoria.

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
