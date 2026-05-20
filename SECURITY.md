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
   `episodic_memory`, `procedural_memory` requieren tests + 1 aprobación
   humana explícita para cualquier migración (regla #3 de `AGENTS.md`).

5. **JWT firmado con secret rotable.** Token expira en 7 días por
   defecto (configurable). Refresh requiere re-autenticación si pasó
   más de 30 días.

6. **TLS end-to-end.** En producción, tráfico Cloudflare Tunnel →
   FastAPI siempre cifrado. En dev local, HTTPS con mkcert.

7. **Backups cifrados.** pg_dump de la DB con cifrado AES-256 antes
   de subir a R2.

8. **Audit log.** Cada acceso a memoria del usuario queda registrado
   con timestamp, modo y origen (modelo o tool).

## Datos personales y borrado

El usuario tiene derecho a:

- Exportar toda su memoria y conversaciones
  (`scripts/export-user-data.sh`).
- Borrar todo (`scripts/reset-memory.sh`).
- Pausar la memoria semántica de forma temporal.

Detalle de implementación en
[`docs/product/MEMORY.md`](./docs/product/MEMORY.md).

## Dependencias

- Cualquier dependencia nueva pasa por review humano.
- Auditoría automática semanal con `pnpm audit` y `uv pip audit`.
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
