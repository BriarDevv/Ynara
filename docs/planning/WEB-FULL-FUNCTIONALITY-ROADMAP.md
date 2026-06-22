# Roadmap: Web a funcionalidad completa (salir de mock-first)

> Estado: vivo · Última actualización: 2026-06-22
> Dueño del orden: agente (autonomía dada por @BriarDevv — "mejor práctica, lo más
> escalable posible"). Cada PR con migración requiere **1 aprobación humana** (regla #3).

## Objetivo

Que la **web (`apps/web`) ande con todas las funcionalidades de Ynara** contra el
backend real, no contra mocks. Ya validamos la IA 10/10 en el playground admin
(gemma/qwen vía Ollama). Falta llevar eso a la web: chat, modos, memoria, agenda,
recaps, onboarding persistido — y la **capa qwen por detrás** (memoria + agendado +
tools automáticos).

## Hallazgo de la auditoría (2026-06-22)

El **backend está más adelante que la web**. Tres categorías:

1. **Ya real, solo apagar mocks** (`NEXT_PUBLIC_ENABLE_MOCKS=false`): auth, chat
   (stream), onboarding (cierre), perfil, **memoria** (ver/editar/borrar/exportar/
   wipe **y búsqueda** — el contrato calza exacto), modos (`GET /v1/modes`).
2. **Backend listo, falta cablear web**: historial de chat real (`GET /v1/sessions`).
3. **Sin backend (laburo nuevo)**: agenda, tareas, recap, sugerencias, avisos, y los
   **tools por chat** (calendar/reminder `not_wired`).

Sub-hallazgo clave: **tareas, recap y sugerencias NO son CRUD manual** — el contrato
(`today.ts`) las marca como generadas por el LLM ("a partir de memoria + tareas +
agenda"). Convergen todas en la **capa qwen por detrás** ([ADR-021](../architecture/adrs/ADR-021-qwen-pasada-asincrona-agente.md)).

## Arquitectura de la capa "qwen por detrás" (lo escalable)

La pasada del agente es **asíncrona** (Celery), no síncrona en el request del chat:
gemma responde/streamea ya; qwen hace la pasada después (anota memoria, agenda,
recuerda, usa tools) sin bloquear la UX. Reusa el patrón ya probado de
`consolidate_turn`. Qué corre se decide por **config de modo** (`tools_enabled` /
`writes_memory` en `ynara.config.json`), no por código. Detalle completo en
**[ADR-021](../architecture/adrs/ADR-021-qwen-pasada-asincrona-agente.md)**.

## Restricción de orden: cadena de migraciones

Las migraciones Alembic son una cadena lineal de un solo head. Toda fase con tabla
nueva (agenda, onboarding, tasks, reminders) encadena con la anterior: o va **stacked**
sobre la rama previa, o espera a que esa rama se mergee a `main`. Las fases sin
migración (frontend un-mock, recap leyendo episódica, docs) no tienen esta restricción.

## Secuencia (orden recomendado)

| # | Fase | Migración | Depende de | Estado |
|---|------|-----------|-----------|--------|
| C | **Agenda backend** (`CalendarEvent` + `/v1/events` CRUD) | sí (gated) | — | ✅ PR #402 (abierto) |
| A | **Frontend un-mock**: web → backend real para lo ya real (memoria/chat/perfil/búsqueda) + historial `/v1/sessions` | no | — | pendiente |
| E1 | **Tool `calendar` real** (`create_event`/`list_events` → `calendar_events`) detrás de interfaz | no | C (merge) | pendiente |
| E2 | **Pasada async del agente** (`agent_turn_pass` Celery, gated por `tools_enabled`) — ADR-021 | no | E1 | pendiente |
| B | **Onboarding persistido** (mood / interested_modes / retención en DB) | sí (gated) | — | pendiente |
| D1 | **Tasks backend** (`Task` + CRUD) — valor real recién con E2 generando tareas | sí (gated) | — | pendiente |
| D2 | **Recap** (`GET /v1/recap` leyendo consolidación episódica) | no | worker Celery | pendiente |
| F | **Avisos / reminders** (tabla `reminders` + scheduler + feed que surfacea las acciones de E2) | sí (gated) | E2 | pendiente |

Notas:
- **A** se puede hacer ya, sin esperar merges ni migraciones (sidestea la cadena).
- **E1/E2** son el corazón ("pasa por atrás la capa"); arrancan con #402 en `main`.
- **D2/E2/F** dependen del **worker Celery** corriendo (la auditoría marcó
  `celery beat no deployado` como CRITICAL — resolver para prod).

## Decisiones tomadas (autónomas, best-practice)

- **Agenda**: CRUD manual (#402) + auto-agendado por chat (E2, tool calendar).
- **Memoria/tools "siempre" vs por modo**: resuelto **por config** (`tools_enabled` /
  `writes_memory`), no hardcode (ADR-021 D5). El producto lo cambia por data.
- **`GET /v1/events` sin LIMIT**: la web filtra día/semana client-side; el filtrado
  real `?from=&to=` es fase posterior (ADR-018 §3). Sin cap arbitrario que silencie
  eventos futuros.

## Verificación (estándar por fase)

- Backend con tests **integration** contra Postgres+pgvector dedicado
  (`TEST_DATABASE_URL=127.0.0.1`, marker `-m integration`) + **unit** con
  `LLM_BACKEND=fake EMBEDDING_BACKEND=fake RERANKER_BACKEND=fake`.
- Migraciones: `alembic upgrade head` + roundtrip downgrade/upgrade contra la DB de test.
- `ruff check` + `ruff format` + `scripts/check_doc_catalogs.py`.
- Pasada separada de `code-reviewer` (y `security-reviewer` en la capa de tools).
- Frontend: `tsc` + lint + tests del web; E2E browser cuando haya stack corriendo.

## Gates (no negociables — AGENTS.md)

- Sin commit/push/merge sin OK humano para `main` (regla #1). `main` solo por PR
  mergeado en GitHub.
- Migraciones (`alembic/versions/`) + `app/memory/`: 1 aprobación humana en el PR (regla #3).
- Logs: solo `type(exc).__name__` (regla #4).
