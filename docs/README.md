# Mapa de docs/

Toda la documentación canónica de Ynara vive acá, organizada por
audiencia y tipo.

## Estructura

```
docs/
├── architecture/      # Decisiones técnicas, diagramas, ADRs
│   ├── adrs/          # Architecture Decision Records (uno por decisión)
│   ├── diagrams/      # Diagramas del sistema (markdown + mermaid)
│   └── informe-tecnico.pdf  # Informe técnico fundacional (Mayo 2026) con bitácora de versiones
├── product/           # Visión, modos, memoria, voz
├── operations/        # Instalación, deploy, runbook, migraciones
└── conventions/       # Commits, glosario, AI guidelines, code style
```

## Por audiencia

| Sos... | Empezá por |
|--------|------------|
| Dev frontend nuevo | `conventions/CODE-STYLE.md`, `product/MODES.md`, `../DESIGN.md` |
| Dev backend nuevo | `architecture/adrs/`, `product/MEMORY.md`, `../apps/backend/AGENTS.md` |
| Diseño / producto | `product/VISION.md`, `product/MODES.md`, `../IDENTITY.md` |
| Ops / deploy | `operations/INSTALL.md`, `operations/DEPLOY.md`, `operations/RUNBOOK.md` |
| IA / agente externo | `../AGENTS.md`, `conventions/AI-GUIDELINES.md` |

## Reglas de la doc

- Markdown plano siempre. Sin frameworks de docs todavía (mkdocs,
  docusaurus) — agregar requiere ADR.
- Diagramas en Mermaid embebido en `.md`. Si necesitás algo más
  complejo, exportar PNG/SVG a `architecture/diagrams/` y referenciar.
- ADRs son inmutables una vez aprobados. Cambiar una decisión =
  crear un ADR nuevo que supersede al viejo.
- Cada cambio sustantivo a docs pasa por PR, no es free-for-all.

## Para el `informe-tecnico.pdf`

El informe técnico fundacional del proyecto vive en
`docs/architecture/informe-tecnico.pdf` (Mayo 2026). Es la pieza de
referencia que explica el **por qué** de cada decisión técnica
(modelos, memoria, infra, posicionamiento).

El informe trae al final una **bitácora de actualizaciones de
versión**. Cuando una versión puntual del stack avance (Next.js
16 → 17, Expo 53 → 54, etc.), se agrega una línea a esa bitácora
y se actualizan los manifests correspondientes (`package.json`,
`pyproject.toml`, `ynara.config.json`).

Los cambios de **decisión arquitectónica** (cambiar Mem0 por otro
engine, cambiar vLLM por otro server, etc.) **no** se reflejan
editando el informe: se hacen vía ADR nuevo en
`docs/architecture/adrs/`, que supersede al ADR previo.
