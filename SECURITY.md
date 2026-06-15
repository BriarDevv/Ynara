# SECURITY.md — Política de seguridad de Ynara

## Reportar una vulnerabilidad

Si encontraste una vulnerabilidad, **no la reportes en un issue
público**. Usá la funcionalidad **Private Vulnerability Reporting
(PVR)** de GitHub, que es la versión privada y trackeable del flow
de issues para reportes de seguridad.

### Cómo reportar

1. Andá a
   [github.com/BriarDevv/Ynara/security/advisories](https://github.com/BriarDevv/Ynara/security/advisories/new).
2. Click en **"Report a vulnerability"**.
3. Completá:
   - Descripción de la vulnerabilidad.
   - Pasos para reproducirla.
   - Impacto estimado (qué datos / qué función queda expuesta).
   - Si conocés una mitigación, sugerirla.

Te respondemos dentro de **72 horas hábiles**. Si la vulnerabilidad
es crítica (data exfiltration, RCE, auth bypass), la prioridad
salta a inmediata.

> Si PVR no aparece habilitado, pedir a un admin del repo que lo
> active en `Settings → Code security and analysis → Private
> vulnerability reporting → Enable`.

### Issues normales

Para bugs no-sensibles, features, o cualquier otro tipo de tema
público, usar
[github.com/BriarDevv/Ynara/issues](https://github.com/BriarDevv/Ynara/issues)
con el template correspondiente.

## Principios

Ynara maneja datos personales sensibles (memoria conversacional,
agenda, recordatorios). La política de seguridad refleja eso:

1. **Datos del usuario nunca salen del perímetro.** Toda la
   inferencia es on-prem. Prohibido enviar mensajes, memoria o
   metadata a OpenAI, Anthropic, Google u otras APIs externas (regla
   #4 de `AGENTS.md`).

2. **Secrets nunca en el código.** Variables de entorno solo.
   `.env*` está gitignored. Si detectás un secret commiteado:
   rotación inmediata + reporte.

3. **Autorización en FastAPI, no en la DB.** Durante fase MVP usamos
   Supabase como Postgres gestionado, pero prohibido usar Supabase
   RLS como mecanismo de autorización primaria. La autorización vive
   en la API (regla #5 de `AGENTS.md`).

4. **Tablas de memoria son sagradas.** `semantic_memory`,
   `episodic_memory`, `procedural_memory` y el audit trail inmutable
   `audit_log` requieren tests + 1 aprobación humana explícita para
   cualquier migración (regla #3 de `AGENTS.md`).

5. **JWT firmado con secret rotable.** El access token expira en 7 días
   por defecto (`JWT_EXPIRE_MINUTES`); el refresh token en 30 días
   (`JWT_REFRESH_EXPIRE_MINUTES`). El refresh es **single-use con
   reuse-detection a nivel familia** (claim `sid`): un retry dentro de la
   ventana de gracia (`AUTH_REFRESH_REUSE_GRACE_SECONDS`, 30s) es idempotente
   (converge en el sucesor canónico, no revoca nada); un reuse fuera del grace
   es un **breach** → revoca la **familia entera** (todos los access + refresh
   de esa sesión) → 401. `/v1/auth/logout` revoca la **sesión completa**
   (familia vía `sid`: refresh + access hermanos), además de los `jti`
   individuales (compat pre-#142). La revocación es **fail-open**: si Redis cae,
   degrada al baseline JWT-stateless (el token vale hasta su `exp`).

6. **TLS end-to-end.** En producción, tráfico Cloudflare Tunnel →
   FastAPI siempre cifrado. En dev local, HTTPS con mkcert.

7. **Backups cifrados.** pg_dump de la DB con cifrado AES-256 antes
   de subir a R2.

8. **Audit log.** Cada acceso a memoria del usuario queda registrado
   con timestamp, modo y origen (modelo o tool).

## Datos personales y borrado

El usuario tiene derecho a:

- Exportar toda su memoria y conversaciones: `GET /v1/memory/export`
  (devuelve las 3 capas descifradas con su propio JWT).
- Borrar todo: `POST /v1/memory/wipe` (con `?dry_run=true` previsualiza el
  recount sin borrar; el execute destructivo exige el confirm per-layer).
- Pausar la memoria semántica de forma temporal.

> Los scripts `scripts/export-user-data.sh` y `scripts/reset-memory.sh`
> son **placeholders** (hoy `exit 1` / sin implementar): la superficie real
> es la API de FastAPI de arriba.

Detalle de implementación en
[`docs/product/MEMORY.md`](./docs/product/MEMORY.md).

## Dependencias

- Cualquier dependencia nueva pasa por review humano.
- Auditoría automática de dependencias del backend con `uv run pip-audit`,
  disparada en cada PR/push que toca `apps/backend/**` (CI de backend,
  `.github/workflows/ci.yml`); falla el build ante una CVE/PYSEC conocida.
  El frontend todavía no tiene auditoría de dependencias automatizada.
- Pin de versiones obligatorio para dependencias críticas (auth,
  crypto, ORM).

## Modelo de amenaza (resumen)

<!-- TODO: completar threat model formal cuando armemos el doc -->

Adversarios considerados:

- Atacante externo intentando acceso a memoria de usuarios.
- Insider con acceso a la VPS de producción.
- Cliente comprometido (token robado).

No considerados (por ahora):

- Análisis side-channel de inferencia.
- Ataques físicos a la GPU.
