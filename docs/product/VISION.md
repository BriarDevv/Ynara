# VISION.md — Visión de Ynara

<!-- TODO: refinar con el equipo en sesión de visión -->

## A 1 año (MVP → product-market fit)

Ynara como herramienta personal real: 500-1000 usuarios activos en
LATAM (arranque Argentina) que dependen de Ynara para productividad
+ memoria personal. Métricas eje:

- Retención semana 4 > 30%.
- Mensajes promedio por usuario activo / semana.
- % de acciones cerradas por tools sobre acciones intentadas.
- NPS interno > 40.

## A 3 años (escala)

Ynara como infraestructura propia de asistencia personal en
español. 50K-200K usuarios activos. Tres planos:

1. **Producto**: app multi-modo con memoria propia, sin lock-in a big
   tech.
2. **Plataforma**: tools de tercero pueden conectarse vía API
   controlada (calendar de terceros, etc.).
3. **Infra**: stack 100% on-prem; capacidad de offering enterprise
   bajo demanda (B2B, instituciones educativas).

## Ventaja defensiva

- **Infra propia**: no dependemos de OpenAI/Anthropic/Google. No nos
  cambian las reglas overnight.
- **Memoria propia**: el dato es del usuario, vive donde nosotros lo
  ponemos. Los gigantes tienen incentivos opuestos.
- **Tono y lengua**: rioplatense específico, no traducido. Difícil de
  copiar a escala global.
- **Modelos especializados**: dual stack (Gemma + Qwen) entrenado en
  nuestros datos, no en datos genéricos.

## Lo que **no** somos

- No somos un wrapper de GPT. No vamos a ese juego.
- No somos un terapeuta. No queremos serlo.
- No somos un agente generalista que hace todo. Somos un asistente
  **personal**, con foco.

## Equipo

3 personas (@MateoGs013, @BriarDevv, @querques20). Hardware:
RTX 4080 Super 16GB para inferencia + fine-tuning. Stack
TypeScript + Python.

## Riesgos identificados

- VRAM límite con dos modelos grandes simultáneos → mitigación: vLLM
  con LRU + cuantización.
- Costo de DevOps en V2 cuando se migra a self-hosted → mitigación:
  ADR-005 separa fases.
- Burnout del equipo chico → mitigación: scope acotado por modo,
  features se cierran completas antes de la siguiente.

## Open questions

<!-- TODO: respuestas con el equipo -->
- Modelo de negocio: freemium + paid tier vs solo paid.
- Aplicación enterprise (B2B educativo) — ¿desde cuándo?
- Open source de parte del stack — ¿qué partes y cuándo?
