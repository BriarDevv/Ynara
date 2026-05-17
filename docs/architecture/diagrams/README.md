# docs/architecture/diagrams/

Diagramas del sistema en Mermaid embebido en `.md`. Cuando un diagrama
necesite editor visual, exportar PNG/SVG y referenciar el archivo.

## Diagramas actuales

- [`flow-mensaje.md`](./flow-mensaje.md) — flujo de un mensaje desde
  el cliente hasta la respuesta, pasando por router LLM, tools y
  memoria.
- [`memoria-3-capas.md`](./memoria-3-capas.md) — modelo de memoria
  semántica + episódica + procedural y cómo interactúan.
- [`deploy-topology.md`](./deploy-topology.md) — topología de
  deploy: Cloudflare, Vercel, VPS, GPU, Supabase (MVP) → self-hosted
  (V2).

## Convención

- Markdown + bloques mermaid.
- Si un diagrama crece más de 80 líneas mermaid, evaluar exportar a
  SVG y dejar el `.md` como índice.
- Cambiar un diagrama requiere PR.
