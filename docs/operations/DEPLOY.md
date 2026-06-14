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
- **GPU inference** → vLLM en máquina con RTX 4080 Super.
  _(PENDIENTE: track de infra aparte; hoy el backend usa `FakeLlmClient`.
  La integración ya está soportada vía `LLM_SERVING` (ADR-013): lista de
  procesos `{base_url, models}`.)_

## Pipelines CI/CD

GitHub Actions:
- `.github/workflows/ci.yml` — lint + typecheck + tests en cada PR.
- `.github/workflows/deploy-web.yml` — deploy a Vercel en push a
  `main`.
- `.github/workflows/deploy-mobile.yml` — trigger EAS Build manual
  (workflow_dispatch).
- `.github/workflows/deploy-backend.yml` — build Docker + push +
  deploy a VPS (manual o tag).

## Web (Vercel)

- Conectar el repo a Vercel apuntando a `apps/web`.
- Variables de entorno desde el dashboard de Vercel.
- Preview por PR automático.
- Production en push a `main`.

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

## vLLM

> **(PENDIENTE — infra track aparte; el servidor de inferencia real
> aún no está provisionado.)**

`./infra/vllm/start-vllm.sh` corre Gemma y Qwen en puertos
separados. Para producción, systemd unit que lo levante al boot.
Ver `infra/vllm/README.md` (TODO completar).

## Migración a V2

Cuando llegue el momento de mover de Supabase a Postgres self-hosted,
seguir `MIGRATION-SUPABASE-TO-SELFHOSTED.md`.

## Open questions

<!-- TODO -->
- Estrategia de blue/green vs rolling para backend.
- Window de mantenimiento estándar.
- Monitoring stack (Grafana + Loki vs Sentry-only).
