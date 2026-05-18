---
name: Bug report
about: Reportar un comportamiento inesperado en Ynara
labels: bug
---

## Resumen

<!-- Qué pasa, en 1-2 líneas. -->

## Comportamiento esperado

## Comportamiento actual

## Pasos para reproducirlo

1.
2.
3.

## Entorno

- App afectada: [ ] web · [ ] mobile · [ ] backend · [ ] infra · [ ] docs
- Modo (si aplica): [ ] productividad · [ ] estudio · [ ] bienestar · [ ] vida · [ ] memoria · [ ] global
- OS:
- Browser o device:
- Commit / branch donde se reprodujo:
- Lockfiles cargados (`pnpm-lock.yaml`, `apps/backend/uv.lock`)? [ ] sí · [ ] no — regla #1

## Logs, errores, screenshots

<!--
Stack trace completo, output del error o screenshot. Bloque de código
para texto, attachment para visual.
-->

```text

```

## Severidad estimada

- [ ] **blocker** — bloquea desarrollo o expone data sensible
- [ ] **mayor** — afecta una feature crítica con workaround duro
- [ ] **menor** — molesta pero hay workaround viable

## Reglas potencialmente involucradas

<!-- Marcar si el bug toca alguna de las 10 reglas no negociables. -->

- [ ] Toca tablas sagradas — `semantic_memory` / `episodic_memory` / `procedural_memory` (regla #3)
- [ ] Toca secrets, auth o JWT (regla #2)
- [ ] Datos de usuario podrían haber salido a APIs externas (regla #4)
- [ ] Cliente `@supabase/supabase-js` involucrado en frontend (regla #5)
- [ ] Ninguna de las anteriores

## Hipótesis (opcional)

<!-- Si tenés idea de la causa raíz o de un commit candidato a haber introducido el bug. -->
