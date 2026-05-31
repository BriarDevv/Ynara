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

## Trabajar con vLLM en local

> **Hoy el backend usa `FakeLlmClient` y `FakeEmbeddingClient`** por
> defecto — no se necesita ningún servidor de inferencia para
> desarrollar o correr los tests. Apuntar a vLLM/Ollama real es
> **opcional** y solo aplica cuando el servidor exista.

Si querés apuntar a un servidor de inferencia real (vLLM o Ollama),
configurá las siguientes variables en `apps/backend/.env`:

```sh
# Servidor primario (ej.: vLLM con Qwen en GPU local)
LLM_PRIMARY_BASE_URL=http://localhost:8000/v1

# Servidor secundario (ej.: Ollama como fallback)
LLM_SECONDARY_BASE_URL=http://localhost:11434/v1

# Topología: "single" (un server) o "split_process" (primario+secundario)
LLM_TOPOLOGY=split_process
```

Si usás Ollama como backend:

```sh
ollama serve
ollama pull gemma2:9b-instruct-q5_K_M  # ejemplo, no es el modelo final
ollama pull qwen2.5:7b-instruct-q5_K_M
```

Si tenés GPU NVIDIA y vLLM instalado:

```sh
./infra/vllm/start-vllm.sh  # PENDIENTE — infra track aparte
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
