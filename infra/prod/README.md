# infra/prod/

Configs y notas específicas de producción que no entran en el
docker-compose principal:

- systemd units para vLLM (creadas: ver abajo).
- Cloudflare Tunnel ingress config.
- Cron de backups encriptados a R2.
- Reglas de firewall.
- Tuning Postgres para la fase V2 (cuando se migre a self-hosted).

## systemd units de vLLM (issue #212)

Una unit por proceso, alineadas a ADR-012 (12B conversacional, 9B agente,
`single_process` co-residente, thinking OFF conversacional). Levantar el
stack completo:

```sh
systemctl enable --now vllm-gemma.service vllm-qwen.service vllm-bge.service
```

- [x] [`vllm-gemma.service`](./vllm-gemma.service) — Gemma 4 12B (conversacional, `:8001`).
- [x] [`vllm-qwen.service`](./vllm-qwen.service) — Qwen 3.5-9B (agente, `:8002`).
- [x] [`vllm-bge.service`](./vllm-bge.service) — bge-m3 (embeddings, `:8003`), companion para que el stack co-residente arranque completo.

Los flags (`gpu_memory_utilization`, `max_model_len`) son PROVISIONALES
(medición Ollama/GGUF, ADR-012 D3); reconfirmar bajo vLLM/AWQ-Marlin
(#207). Paths/checkpoints van en `/etc/ynara/vllm.env` (EnvironmentFile),
nunca en la unit (regla #4).

## TODO inicial (pendiente)

- [ ] `cloudflared.yml` con ingress hacia el contenedor api.
- [ ] `backup-db.sh` + crontab para pg_dump diario cifrado.
- [ ] `postgres-tuning.conf` para Postgres self-hosted (V2).
