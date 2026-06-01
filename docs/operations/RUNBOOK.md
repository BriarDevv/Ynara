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

> **(PENDIENTE — aplica cuando vLLM esté deployado; hoy el backend
> usa `FakeLlmClient` y este escenario no aplica en dev/staging.)**

1. `nvidia-smi` → ver utilización GPU.
2. `journalctl -u vllm-qwen -n 200` y `journalctl -u vllm-gemma -n 200`.
3. Si VRAM saturada: bajar batch size o reiniciar un modelo (con
   degradación temporal del modo afectado).

### Worker Celery atascado

1. `docker compose logs worker | tail -200`.
2. Inspeccionar cola: `redis-cli -u $REDIS_URL LLEN celery`.
3. Restart: `docker compose restart worker`.

### Redis caído o degradado

**Síntoma:** `/v1/health/ready` devuelve **503** con `checks.redis.ok=false`.

**Impacto:** la auth pasa a **fail-open** (desde #63 Redis es el store de
blocklist de tokens + rate-limit de login). Con Redis caído:

- La **revocación anticipada** (logout / refresh single-use) se desactiva:
  los tokens valen hasta su `exp` (un logout previo no surte efecto hasta
  que el token expire).
- El **rate-limit** de `/auth/token` y `/auth/register` se desactiva (sin
  throttling aplicativo).

La auth **sigue funcionando** (degrada al baseline JWT-stateless); Celery sí
se ve afectado (broker/result backend).

**Acción:**

1. Verificar el estado: `redis-cli -u $REDIS_URL PING` (espera `PONG`).
2. Reiniciar/verificar Redis: `docker compose restart redis` (VPS) o revisar
   el panel de Upstash si es gestionado.
3. Confirmar recuperación: `/v1/health/ready` vuelve a **200** con
   `checks.redis.ok=true`.

### Revocar la sesión activa de un usuario

Para invalidar la sesión de **un** usuario sin rotar el `JWT_SECRET` global:

1. `POST /v1/auth/logout` con el JWT del usuario (`Authorization: Bearer
   <access>`; opcionalmente su `refresh_token` en el body).
2. El backend revoca la FAMILIA completa de esa sesión (desde #142: todos los
   tokens del mismo `sid` — access, refresh y rotaciones futuras — dejan de
   servir aunque no hayan expirado); para tokens pre-#142 sin `sid`, revoca solo
   el `jti` del access (compat). Requiere Redis arriba; fail-open si cae.

> Requiere Redis arriba (si está caído, la auth está en fail-open y la
> revocación no surte efecto — ver "Redis caído o degradado"). Para revocar
> **todas** las sesiones de golpe, rotar `JWT_SECRET` (ver "Secret expuesto
> en commit").

### App no arranca (RuntimeError del guard anti-prod)

El backend tiene un guard (`app/core/db_guard.py`) que aborta el boot
si `DATABASE_URL` apunta a Supabase (host de producción) y no se
cumple alguna de las condiciones de seguridad.

**Síntoma:** el proceso termina en el arranque con un `RuntimeError`
que menciona el host que disparó el guard.

**Resolución según contexto:**

1. **Dev local** — no usar `DATABASE_URL` de Supabase. Usar la DB
   local de tests:
   ```sh
   DATABASE_URL=postgresql://postgres:test@localhost:5433/ynara_dev
   ```
2. **Conexión a prod intencionada** (ej.: aplicar migración manual) —
   exportar la variable de override antes de arrancar:
   ```sh
   export YNARA_ALLOW_PROD_DB=1
   ```
   Usarlo solo en terminales efímeras y nunca commitear este valor.
3. **Deploy real en producción** — asegurarse de que `ENVIRONMENT=production`
   esté seteado en el entorno del contenedor/proceso.

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
2. Forzar logout de sesiones existentes si era JWT secret. Rotar
   `JWT_SECRET` invalida **todos** los tokens de golpe por firma
   (mecanismo primario, no depende de Redis); el blocklist per-`jti`
   (`/v1/auth/logout`, desde #63) es complementario y solo alcanza tokens
   individuales.
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
