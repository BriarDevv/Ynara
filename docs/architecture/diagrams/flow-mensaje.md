# Flujo de un mensaje en Ynara

<!-- TODO: refinar con detalle de auth, rate limits, telemetría -->

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario (web/mobile)
    participant API as FastAPI /v1/chat
    participant R as Router LLM
    participant M as Memoria
    participant G as Gemma 4 12B (conv)
    participant Q as Qwen 3.5 9B (agente)
    participant T as Tools

    U->>API: POST /v1/chat {text, mode}
    API->>API: Validar JWT + rate limit
    API->>R: route(mode, ctx)
    R->>M: search(query, layers según modo)
    M-->>R: contexto relevante
    alt modo conversacional (bienestar/vida/estudio)
        R->>G: generate(prompt + contexto)
        G-->>R: respuesta texto
    else modo agente (productividad/memoria)
        R->>Q: generate(prompt + contexto + tools)
        Q->>T: tool call (calendar/reminder/memory)
        T-->>Q: tool result
        Q-->>R: respuesta texto + acciones
        R->>M: write(memoria nueva, async vía Celery)
    end
    R-->>API: respuesta final
    API-->>U: 200 OK {text, actions?}
```

## Notas

- La extracción y consolidación de memoria episódica/procedural va
  **siempre asíncrona** vía Celery (regla extendida en
  `docs/conventions/AI-GUIDELINES.md`).
- Gemma nunca escribe memoria. Solo Qwen tiene esa capacidad.
- El router decide modelo según `ynara.config.json[modes][...].model`.
- **Rate-limit todavía no está implementado** (el paso `Validar JWT +
  rate limit` del diagrama es objetivo, no estado actual).
- **Gemma/Qwen son los modelos objetivo.** Hoy el cliente LLM es un
  Fake (`FakeLlmClient`) hasta que el track de infra vLLM esté
  disponible.
