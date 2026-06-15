# DEPLOY.md — Deploy de Ynara

## Topología

Ver `docs/architecture/diagrams/deploy-topology.md`.

- **Web** → Vercel (Next.js 16).
- **Mobile** → Expo EAS Build (iOS + Android).
- **Backend** → VPS LATAM detrás de Cloudflare Tunnel.
- **DB** → Supabase (MVP) → Postgres self-hosted (V2).
- **Cache / queue / auth store** → Redis (Upstash o Docker en VPS).
  **Requerido**: además de caché y broker/result de Celery, desde #63 es
  el store de AUTH (blocklist de tokens para logout/refresh + rate-limit
  de login). La auth degrada a fail-open si Redis cae, pero el servicio
  debe estar provisto.
- **Storage** → Cloudflare R2.
- **GPU inference** → en la 4080 Super 16 GB el motor de serving local es
  **Ollama/GGUF** (ADR-014): un solo endpoint (`:11434`) sirve gemma4 +
  qwen + bge-m3 co-residentes en la misma GPU. **vLLM queda reservado a
  GPU de 24 GB+** (en 16 GB no entran dos LLM por proceso, medido en #207).
  _(El backend default usa `FakeLlmClient`; para apuntar al serving real se
  configura `LLM_SERVING` (ADR-013: lista de `{base_url, models}`) y se
  prende `LLM_BACKEND=vllm` — nombre legacy del cliente OpenAI-compatible,
  sirve igual a Ollama o vLLM.)_

## Pipelines CI/CD

GitHub Actions:
- `.github/workflows/ci.yml` — **Backend CI** scopeada a `apps/backend/**`:
  `ruff check` + `ruff format --check` + `pip-audit` + `pytest` (unit +
  integration con gate de cobertura). No corre typecheck.
- `.github/workflows/ci-web.yml` — **Web CI** scopeada a `apps/web/**` +
  packages compartidos: biome + tsc (typecheck) + vitest + `next build`.
  `apps/mobile` queda **fuera de CI** por ahora (su typecheck falla: los tipos
  de NativeWind no exponen `className`).
- `.github/workflows/deploy-web.yml` — **placeholder** `workflow_dispatch`
  (echo TODO); el deploy real de web lo maneja **Vercel vía Git
  integration** (este slot queda para tareas auxiliares post-deploy).
- `.github/workflows/deploy-mobile.yml` — trigger EAS Build manual
  (workflow_dispatch).
- `.github/workflows/deploy-backend.yml` — build Docker + push +
  deploy a VPS (manual o tag `backend-v*`).

## Web (Vercel)

- Conectar el repo a Vercel apuntando a `apps/web`.
- Variables de entorno desde el dashboard de Vercel.
- Preview por PR automático.
- Production en push a `main`.
- El deploy lo dispara **Vercel vía Git integration**, no GitHub Actions.
  `deploy-web.yml` es un slot manual (`workflow_dispatch`) para tareas
  auxiliares post-deploy (smoke tests, purge de cache, notificaciones).

## Mobile (EAS)

- Build manual con `eas build --profile production --platform all`.
- Submit a stores con `eas submit`.
- Secrets desde el dashboard de EAS (no en el repo).
- Detalle en `apps/mobile/EAS.md`.

## Backend (VPS)

### Build
```sh
docker build -f infra/docker/Dockerfile.backend -t ynara-backend:latest .
```

### Deploy
1. Push de imagen a registry privado.
2. SSH a la VPS.
3. `docker compose -f infra/docker/docker-compose.yml pull`.
4. `docker compose -f infra/docker/docker-compose.yml up -d`.
5. Verificar health: `curl https://api.ynara.app/v1/health`.
6. Verificar logs: `docker compose logs -f api`.

### Rollback
1. `docker compose pull <tag-anterior>`.
2. `docker compose up -d`.
3. Verificar.

## Serving de inferencia

**16 GB (4080 Super) → Ollama/GGUF (ADR-014).** El motor de serving local
es Ollama: un endpoint (`:11434`) con gemma4 + qwen + bge-m3 co-residentes.
Es lo que corre hoy como stack de dev.

**24 GB+ → vLLM.** `./infra/vllm/start-vllm.sh` levanta **3 procesos** (uno
por modelo): Gemma `:8001`, Qwen `:8002`, bge-m3 `:8003`. Esta ruta no entra
en 16 GB (medido en #207); aplica solo a GPU de 24 GB+.

Para producción (ruta vLLM) hay **systemd units por modelo** en
`infra/prod/`: `vllm-gemma.service`, `vllm-qwen.service` y
`vllm-bge.service`. Levantar el stack completo:

```sh
systemctl enable --now vllm-gemma.service vllm-qwen.service vllm-bge.service
```

> **Nota:** el comentario de cabecera de esos `.service` todavía dice "RTX 4080
> Super 16 GB" — quedó stale (pre-ADR-014). Esas units son la ruta **24 GB+**; en
> 16 GB el motor es Ollama y no se usan (pendiente: actualizar ese comentario en
> `infra/prod/`).

Detalle de checkpoints, flags y topología en `infra/vllm/README.md`.

## Migración a V2

Cuando llegue el momento de mover de Supabase a Postgres self-hosted,
seguir `MIGRATION-SUPABASE-TO-SELFHOSTED.md`.

## Open questions

<!-- TODO -->
- Estrategia de blue/green vs rolling para backend.
- Window de mantenimiento estándar.
- Monitoring stack (Grafana + Loki vs Sentry-only).
