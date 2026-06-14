# ADR-002: Dual stack Gemma 4 + Qwen 3.5

> **Actualización (ADR-012):** en hardware de 16 GB el conversacional pasó de Gemma 4 26B-A4B a Gemma 4 12B. Ver [ADR-012](./ADR-012-conversational-model-12b-single-process.md).

## Estado
Aceptado

## Fecha
2026-05-XX  <!-- TODO: fecha exacta cuando se apruebe en PR -->

## Contexto

Ynara necesita dos perfiles de modelo diferentes:

1. **Conversacional** — modos Bienestar, Vida, Estudio. Pide latencia
   baja en charla, buena calidad rioplatense, tono cálido. No
   necesita llamar tools ni escribir memoria.
2. **Agente** — modos Productividad, Memoria. Necesita razonar sobre
   contexto, llamar tools (calendar, reminders, memory), escribir
   memoria estructurada. Tolera más latencia a cambio de
   confiabilidad en tool calls.

Forzar un solo modelo para ambos roles es subóptimo: o pierde calidad
conversacional, o pierde precisión de tool-calling.

## Decisión

- **Gemma 4 26B-A4B** (MoE con 4B activos) → modos conversacionales.
  Lee memoria, no escribe.
- **Qwen 3.5 9B** → modos agente. Lee y escribe memoria, llama tools.

Ambos corren en la RTX 4080 Super 16GB con cuantización (Q4 / Q5)
vía vLLM. Endpoints separados en puertos distintos.

## Consecuencias positivas

- Cada modelo optimizado para su rol.
- Separación de permisos en código: el router LLM solo expone tools
  cuando el modo activo usa Qwen.
- Costo de fine-tuning más bajo: cada modelo se entrena en su
  dominio.
- Posibilidad de upgrade independiente (cambiar Qwen sin tocar
  Gemma).

## Consecuencias negativas

- Hay que mantener dos modelos en VRAM. Cargar/descargar dinámico
  agrega complejidad operativa.
- Dos prompts diferentes para mantener tono coherente entre modos.
- Para usuarios que saltan de modo, hay un hand-off explícito.

## Mitigaciones

- `app/llm/router.py` decide modelo según `ynara.config.json[modes]`.
- vLLM corre los dos modelos en paralelo si la VRAM alcanza; si no,
  alternancia con cache LRU.
- Prompts compartidos viven en `app/llm/prompts/` con secciones por
  modelo.

## Alternativas descartadas

- **Solo Qwen 3.5 9B** para todo: pierde calidad conversacional en
  modos Bienestar/Vida.
- **Solo Gemma 4 26B-A4B**: tool-calling menos confiable a la fecha
  de medición interna.
- **Modelo cerrado externo (GPT-4, Claude)**: viola regla #4
  (datos de usuario fuera del perímetro).
