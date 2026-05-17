# infra/prod/

Configs y notas específicas de producción que no entran en el
docker-compose principal:

- systemd units para vLLM (TODO crear).
- Cloudflare Tunnel ingress config.
- Cron de backups encriptados a R2.
- Reglas de firewall.
- Tuning Postgres para la fase V2 (cuando se migre a self-hosted).

## TODO inicial

- [ ] `vllm-gemma.service` y `vllm-qwen.service` systemd units.
- [ ] `cloudflared.yml` con ingress hacia el contenedor api.
- [ ] `backup-db.sh` + crontab para pg_dump diario cifrado.
- [ ] `postgres-tuning.conf` para Postgres self-hosted (V2).
