# infra/vllm/

Scripts para levantar vLLM con Gemma 4 26B-A4B y Qwen 3.5-9B en la
máquina con RTX 4080 Super 16GB.

## Modelos

- **Gemma 4 26B-A4B** (MoE, 4B activos) → conversacional, puerto 8000.
- **Qwen 3.5-9B** → agente, puerto 8001.

Ambos corren cuantizados (Q4/Q5) para entrar en 16GB de VRAM.

## Comandos

```sh
./start-vllm.sh             # levanta los dos modelos en background
```

Para producción, usar systemd units por modelo en lugar del script
(TODO crear las units en `infra/prod/`).

## Configuración

- `--max-model-len`: ajustado por modelo (Gemma 128k, Qwen 256k).
- `--gpu-memory-utilization`: 0.45 cada modelo para que coexistan
  (TODO: medir y ajustar).
- `--quantization`: AWQ o GPTQ según los pesos disponibles.

## Open questions

<!-- TODO: con el equipo -->
- ¿Cargamos los dos modelos en paralelo o alternancia con LRU?
- Tamaño exacto de cuantización (Q4 vs Q5 vs Q6).
- Si la 4080 satura, ¿offload parcial a CPU o solo uno a la vez?
