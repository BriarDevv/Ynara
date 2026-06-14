# Topología de deploy de Ynara

<!-- TODO: refinar con direcciones / puertos / firewalls específicos -->

## MVP (fase actual)

> **NOTA — Estado actual:** el vLLM real todavía NO corre en ningún
> entorno. El backend usa Fakes (`FakeLlmClient`, `FakeEmbeddingClient`,
> `FakeReranker`) en su lugar. Los nodos `VLLM_G` y `VLLM_Q` del
> diagrama representan el estado objetivo; su activación es un track de
> infra aparte, pendiente.

```mermaid
flowchart TB
    subgraph CDN[Cloudflare]
      CFT[Tunnel]
      CFR2[R2 Storage]
    end

    subgraph VERCEL[Vercel]
      WEB[apps/web<br/>Next.js 16]
    end

    subgraph EAS[Expo EAS]
      MOB[apps/mobile<br/>iOS + Android builds]
    end

    subgraph VPS[VPS Argentina / LATAM]
      direction TB
      API[FastAPI<br/>gunicorn + uvicorn]
      WORK[Celery workers]
      REDIS[Redis<br/>Docker o Upstash]
      VLLM_G[vLLM<br/>Gemma 4 12B]
      VLLM_Q[vLLM<br/>Qwen 3.5 9B]
      GPU[RTX 4080 Super 16GB]
    end

    subgraph SB[Supabase]
      PG[Postgres 16<br/>+ pgvector]
    end

    USER([Usuario]) -->|HTTPS| WEB
    USER -->|HTTPS| MOB
    WEB -->|HTTPS| CFT
    MOB -->|HTTPS| CFT
    CFT --> API
    API --> REDIS
    API --> PG
    API --> VLLM_G
    API --> VLLM_Q
    API -.->|enqueue| WORK
    WORK --> PG
    WORK --> VLLM_Q
    VLLM_G --- GPU
    VLLM_Q --- GPU
    API --> CFR2
```

## V2 (post-validación)

Mismo diagrama pero `SB` (Supabase) reemplazado por un Postgres
self-hosted en la misma VPS o en VPS dedicada. Detalle del cutover en
`docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md`.

## Notas

- La 4080 Super tiene 16 GB de VRAM. Gemma 4 12B (dense) cuantizado
  + Qwen 3.5 9B cuantizado + bge-m3 co-residen dentro de los 16 GB
  (confirmado por medición — ADR-012). En vLLM son 2 procesos en la
  misma GPU (una entrada por modelo en `LLM_SERVING`, ADR-013); en dev
  con Ollama, un endpoint único que sirve ambos. El Gemma 4 26B-A4B original no
  entraba; el cambio a 12B cerró esa restricción de VRAM.
- Cloudflare Tunnel evita abrir puertos en la VPS y oculta IP real.
- R2 para storage de exports de usuario, backups cifrados, assets
  estáticos pesados.
