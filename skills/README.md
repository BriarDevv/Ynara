# skills/

Skills reutilizables para humanos y agentes IA, en formato Anthropic
(SKILL.md por skill).

## Skills

- [`add-new-mode/`](./add-new-mode/) — agregar un modo nuevo al
  producto.
- [`add-llm-tool/`](./add-llm-tool/) — agregar una tool al agente
  Qwen.
- [`add-memory-type/`](./add-memory-type/) — agregar un tipo de
  memoria (proceso pesado, requiere ADR).
- [`adr-create/`](./adr-create/) — crear un Architecture Decision
  Record.
- [`create-ui-component/`](./create-ui-component/) — crear un
  componente UI compartido.

## Convención

Cada skill vive en su carpeta con un `SKILL.md`. El SKILL.md tiene:

- Título.
- Cuándo usar.
- Pre-requisitos.
- Paso a paso.
- Checklist de verificación.
- Links a docs relacionadas.

## Agregar una skill

PR con la carpeta + SKILL.md + entrada en este README.
