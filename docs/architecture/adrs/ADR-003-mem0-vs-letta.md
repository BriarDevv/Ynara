# ADR-003: Mem0 OSS v2 como engine de memoria

## Estado
**Superseded por [ADR-010](./ADR-010-memory-architecture-v2.md)** (engine de
storage de la capa semántica). Mem0 resultó incompatible con el cifrado a nivel
campo (ADR-007 D3): fija su DDL en texto plano y necesita plaintext persistido
para extracción/dedup, sin hook pre-store para cifrar. ADR-010 decide owneear el
storage + la inteligencia in-house detrás de Protocols. **Lo que se mantiene de
este ADR**: el espíritu de "custom hooks propios" para episódica y procedural —
ADR-010 lo generaliza a las tres capas. Mem0 queda relegado, a lo sumo, a
referencia de algoritmo / extractor in-memory (nunca storage).

## Fecha
2026-05-XX  <!-- TODO: fecha exacta cuando se apruebe en PR -->

## Contexto

Ynara tiene memoria estructurada en tres capas (semántica, episódica,
procedural). Hace falta una librería que orqueste: extracción de
hechos, deduplicación, búsqueda semántica, consolidación.

Opciones evaluadas:

1. **Mem0 OSS v2** — librería específica para memoria de agentes,
   con extracción + dedup + store agnóstico. Activa, OSS.
2. **Letta (ex-MemGPT)** — orientada a "agentes con memoria
   persistente", más opinionada sobre la arquitectura del agente.
3. **Construir in-house** — control total, costo de desarrollo alto.

## Decisión

Mem0 OSS v2 como engine de memoria semántica, con custom hooks para
las capas episódica y procedural que son específicas de Ynara.

## Consecuencias positivas

- Extracción y dedup ya resueltos.
- Store agnóstico → conectamos Postgres + pgvector (ADR-004) sin
  fricción.
- OSS, sin lock-in vendor.
- Comunidad activa, updates frecuentes.

## Consecuencias negativas

- Mem0 es opinionado sobre el formato de "memory record". Nuestras
  capas episódica y procedural no encajan perfecto.
- Versión v2 todavía con breaking changes posibles.

## Mitigaciones

- Wrapper propio en `apps/backend/app/memory/semantic.py` que
  encapsula Mem0; si en V2 hay que cambiarlo, solo se toca ese
  archivo.
- Tests de regresión sobre la API interna de memoria.

## Alternativas descartadas

- **Letta**: arquitectura demasiado opinionada, fuerza patrones de
  agente que no encajan con nuestro dual-model.
- **In-house**: el costo de desarrollo no se justifica en MVP.
- **Vector DB pura sin engine**: hay que reimplementar extracción y
  dedup, que es justo lo que Mem0 resuelve.
