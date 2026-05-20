# RUNBOOK.md — Incidentes y respuesta

> "Algo se rompió en producción, ¿qué hago?". Esta guía.

## Severidades

- **S0**: producción caída para todos los usuarios.
- **S1**: feature crítica rota (login, chat, memoria) para un subset.
- **S2**: degradación parcial, sin pérdida de datos.
- **S3**: feature secundaria rota, no urgente.

## Contactos

<!-- TODO: completar -->
- On-call principal: @MateoGs013
- On-call secundario: @BriarDevv
- DBA (memoria): @querques20

## Comandos rápidos

| Qué | Cómo |
|-----|------|
| Health del backend | `curl https://api.ynara.app/v1/health` |
| Logs backend (VPS) | `docker compose logs -f api` |
| Logs Celery | `docker compose logs -f worker` |
| Logs vLLM | `journalctl -u vllm-gemma -f` |
| Estado de la DB | `psql $DATABASE_URL -c "SELECT now();"` |
| Backup ad-hoc | `pg_dump $DATABASE_URL | gzip > backup-$(date +%F).sql.gz` |

## Escenarios comunes

### Backend no responde

1. `curl https://api.ynara.app/v1/health` → si no llega, problema de
   Cloudflare Tunnel o del proceso.
2. SSH a VPS: `docker compose ps`.
3. Si `api` está down: `docker compose logs api | tail -200`.
4. Restart: `docker compose restart api`.
5. Si persiste, rollback al tag anterior (ver `DEPLOY.md`).

### Latencia alta en inferencia

1. `nvidia-smi` → ver utilización GPU.
2. `journalctl -u vllm-qwen -n 200` y `journalctl -u vllm-gemma -n 200`.
3. Si VRAM saturada: bajar batch size o reiniciar un modelo (con
   degradación temporal del modo afectado).

### Worker Celery atascado

1. `docker compose logs worker | tail -200`.
2. Inspeccionar cola: `redis-cli -u $REDIS_URL LLEN celery`.
3. Restart: `docker compose restart worker`.

### DB Supabase lenta o caída

1. Status page Supabase.
2. Plan de fallback: solo lectura desde un read replica si está
   configurado <!-- TODO: confirmar si lo tenemos -->.
3. Si Supabase está caído > 30 min: comunicación al usuario por la
   app (banner) + waiting room.

### Memoria de un usuario corrupta

1. Snapshot inmediato: `pg_dump --table=semantic_memory --table=episodic_memory --table=procedural_memory $DATABASE_URL > snapshot.sql`.
2. Identificar el `user_id` afectado.
3. **NO** tocar las tablas sin review humano explícito (regla #3:
   1 aprobación humana además del operador). Crear ticket de
   seguridad inmediato.

### Secret expuesto en commit

1. Rotar el secret inmediatamente.
2. Forzar logout de sesiones existentes si era JWT secret.
3. Borrar el secret del histórico de git (BFG o git filter-repo).
4. Force push solo con autorización explícita (regla #1).
5. Post-mortem.

## Post-mortem template

<!-- TODO: completar template -->

- Timeline.
- Causa raíz.
- Impacto a usuarios.
- Acciones tomadas.
- Acciones preventivas (con dueño + fecha).
