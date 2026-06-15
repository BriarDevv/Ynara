# LOCAL-DEV.md — Flujo de desarrollo diario

> Asume que ya hiciste el INSTALL.md una vez.

## Levantar el stack

Opción rápida con Make:

```sh
make docker-dev-up   # Redis local
make dev-backend     # FastAPI :8080
make dev-web         # Next.js :3000
```

En 3 terminales separadas, o usando un multiplexer (tmux,
WezTerm, ConEmu).

## Flujo típico

1. Crear branch desde `main`:
   `git checkout -b feat/web-modo-bienestar`.
2. Editar código.
3. Lint + format:
   - JS/TS: `pnpm biome check --apply`.
   - Python: `cd apps/backend && uv run ruff check . --fix && uv run ruff format .`.
4. Tests:
   - `pnpm turbo test`.
   - Backend: `cd apps/backend && uv run pytest`.
5. Commit (Conventional Commits en español):
   `git commit -m "feat(web): agregar layout base del modo bienestar"`.
6. PR contra `main` con el template.

## Trabajar con la DB

- Migraciones: ver `apps/backend/docs/MIGRATIONS.md`.
- Reset de memoria local (DESTRUCTIVO):
  `make reset-memory`.

## Trabajar con serving real (Ollama / vLLM)

> **Hoy el backend usa `FakeLlmClient` y `FakeEmbeddingClient`** por
> defecto (`LLM_BACKEND=fake`) — no se necesita ningún servidor de
> inferencia para desarrollar o correr los tests. Apuntar al serving real
> es **opcional**.

El motor de serving local en 16 GB (4080 Super) es **Ollama/GGUF**
(ADR-014): un solo endpoint (`:11434`) que sirve todos los modelos
co-residentes. vLLM queda reservado a GPU de **24 GB+** (en 16 GB no
entran dos LLM por proceso, medido en #207).

Para apuntar al serving real, configurá en `apps/backend/.env`:

```sh
# LLM_SERVING (ADR-013): lista JSON de endpoints, cada uno {base_url, models}.
# Los served_name (gemma4/qwen) salen de ynara.config.json[models].
# Default (Ollama, 16 GB): UN endpoint sirve todos los modelos.
LLM_SERVING=[{"base_url":"http://localhost:11434/v1","models":["gemma4","qwen"]}]
# vLLM (24 GB+): un proceso por modelo, distintos puertos.
# LLM_SERVING=[{"base_url":"http://localhost:8001/v1","models":["gemma4"]},{"base_url":"http://localhost:8002/v1","models":["qwen"]}]

# Prender el cliente real: REEMPLAZÁ el LLM_BACKEND=fake que trae .env.example
# por 'vllm' (no agregues una segunda línea). 'vllm' es el nombre legacy del
# cliente OpenAI-compatible: NO implica vLLM, hoy apunta a Ollama.
LLM_BACKEND=vllm
```

Si usás Ollama (default 16 GB):

```sh
ollama serve
ollama pull gemma2:9b-instruct-q5_K_M  # ejemplo, no es el modelo final
ollama pull qwen2.5:7b-instruct-q5_K_M
```

Si tenés GPU de 24 GB+ y vLLM instalado (3 procesos: gemma :8001 /
qwen :8002 / bge :8003):

```sh
./infra/vllm/start-vllm.sh
```

## Hot reload

- Web: Next.js auto-reload.
- Mobile: Expo auto-reload.
- Backend: `--reload` en uvicorn.
- Workers Celery: requieren restart manual al cambiar código de
  tasks. `make dev-backend` por ahora no levanta el worker; ver
  `apps/backend/AGENTS.md` para correrlo aparte.

## Trucos

- `pnpm turbo run dev --filter web --filter backend` levanta solo
  esos dos.
- `pnpm biome check --apply` antes de commitear suele evitar
  reverts.
- Para debuggear queries SQL de SQLAlchemy: setear
  `SQLALCHEMY_ECHO=1` en `.env`.

## Convención de archivos chicos

- TS strict: target menos de 300 líneas por archivo, refactor si
  pasa de 500.
- Python: idem.
- Si necesitás romper la regla, justificalo en PR.
