# infra/

Infraestructura: Docker, vLLM, prod.

## Subcarpetas

- `docker/` — docker-compose para dev y prod, Dockerfile del backend.
- `vllm/` — scripts para correr vLLM con Gemma + Qwen.
- `prod/` — notas y configs específicas de producción (systemd
  units, Cloudflare Tunnel config, etc.).

## Notas

- En fase MVP, Postgres vive en Supabase, así que el
  `docker-compose.dev.yml` **no** levanta Postgres. Solo Redis.
- En V2, agregar Postgres + pgvector al compose de prod.
