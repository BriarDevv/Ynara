## Qué cambia

<!-- Descripción concisa del cambio en 2-3 líneas -->

## Por qué

<!-- Contexto, problema que resuelve, link a issue si aplica -->

## Tipo de cambio

- [ ] feat: nueva funcionalidad
- [ ] fix: corrección de bug
- [ ] refactor: cambio interno sin afectar comportamiento
- [ ] docs: solo documentación
- [ ] chore: tooling, configs, dependencies
- [ ] test: agregar o corregir tests

## Scope

- [ ] web
- [ ] mobile
- [ ] backend
- [ ] docs
- [ ] infra
- [ ] otro:

## Checklist

- [ ] Conventional Commits en español, imperativo
- [ ] Tests pasando localmente
- [ ] Tipos completos (TS strict / Pydantic)
- [ ] Archivos menos de 300 líneas (o justificación)
- [ ] Sin secrets en el código
- [ ] Sin llamadas a APIs externas con datos de usuario
- [ ] Sin uso del cliente Supabase desde frontend
- [ ] Si tocó migración Alembic: documentada y con rollback
- [ ] Si tocó tablas de memoria: review humano confirmado

## Para IAs revisando este PR

- Leer `AGENTS.md` antes de aprobar
- Verificar reglas no negociables 1-5
- Cualquier duda → pedir review humano, no aprobar
