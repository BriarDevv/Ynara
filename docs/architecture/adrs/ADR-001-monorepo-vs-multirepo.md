# ADR-001: Monorepo vs multirepo

## Estado
Aceptado

## Fecha
2026-05-XX  <!-- TODO: fecha exacta cuando se apruebe en PR -->

## Contexto

Ynara tiene tres apps (web, mobile, backend) y necesita compartir
types, schemas Zod, configuración de tooling. Hay dos enfoques:

1. **Monorepo** — todo en un solo repo con pnpm workspaces +
   Turborepo. Comparte tipos y configs vía packages internos.
2. **Multirepo** — un repo por app, paquetes compartidos publicados
   privadamente (npm registry interno).

## Decisión

Monorepo con pnpm + Turborepo. El backend Python convive con el
frontend TS aunque uv y pnpm sean sistemas distintos.

## Consecuencias positivas

- Cambios cross-cutting (ej: agregar un campo a `MemoryRecord`) se
  hacen en un PR único, atómico.
- TS strict sharing entre web y mobile sin overhead de publicación.
- Tooling consistente: un solo Biome, un solo formato de commits.
- Turborepo cachea builds entre apps.
- Onboarding más simple: un solo clone.

## Consecuencias negativas

- pnpm y uv son ecosistemas distintos. Hay que coordinarlos a mano.
- Repo crece rápido. Tiempo de clone/CI puede subir.
- Ramas más ruidosas si no se respeta scope en commits.

## Mitigaciones

- `turbo.json` segmenta tareas por app: lo que no cambió, no se
  rebuildea.
- `.gitignore` agresivo con node_modules, .next, .venv, modelos.
- Conventional Commits con scope obligatorio para apps.

## Alternativas descartadas

- **Nx**: más opinionado, curva de aprendizaje mayor. Turborepo es
  más liviano y suficiente.
- **Multirepo con paquetes privados**: overhead administrativo alto
  para un equipo de 3.
