# SKILL: Agregar un tipo de memoria nuevo

## Cuándo usar

Cuando se necesita una capa de memoria adicional más allá de las 3
actuales (semántica, episódica, procedural). **Este es un cambio
muy grande**: probablemente no es lo que querés. Considerá si
encaja en una capa existente primero.

## Pre-requisitos

- ADR aprobado **con discusión amplia del equipo**.
- Aprobación explícita de @MateoGs013, @BriarDevv y @querques20
  (todos los CODEOWNERS).
- Plan claro de qué memoria existente no cubre el caso.

## Paso a paso

1. **ADR**. Obligatorio. Crear `docs/architecture/adrs/ADR-XXX-`
   con:
   - Por qué las 3 capas existentes no alcanzan.
   - Schema propuesto.
   - Cómo interactúa con las otras capas (¿se duplican datos?).
   - Plan de backfill / retrocompatibilidad.
2. **Migración Alembic**. La migración crea la nueva tabla. Tabla
   nueva = tabla sagrada (regla #3) — requiere tests + 2 aprobaciones.
3. **Modelo SQLAlchemy** en `apps/backend/app/models/`.
4. **Wrapper** en `apps/backend/app/memory/<nombre>.py` con
   funciones `add`, `search`, `update`, `delete` (mismo shape que
   las existentes).
5. **`ynara.config.json`**: agregar a la lista de
   `memory_layers` válidos donde aplique por modo.
6. **`docs/product/MEMORY.md`**: documentar la nueva capa, política
   de retención, derechos del usuario.
7. **`apps/backend/docs/MODELS.md`**: agregar entrada con 🔴.
8. **Workflow de consolidación** si aplica:
   `apps/backend/app/workflows/`.
9. **Tests**: integración completa con DB real, incluyendo migración
   up + down.
10. **PR**: 2 aprobaciones humanas obligatorias.

## Checklist

- [ ] ADR aprobado.
- [ ] Migración Alembic con downgrade.
- [ ] Modelo SQLAlchemy.
- [ ] Wrapper de memoria.
- [ ] `ynara.config.json` actualizado.
- [ ] `docs/product/MEMORY.md` actualizado.
- [ ] `docs/MODELS.md` actualizado con 🔴.
- [ ] Tests pasando.
- [ ] **2 aprobaciones humanas** en el PR.
