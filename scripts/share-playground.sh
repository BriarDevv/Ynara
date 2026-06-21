#!/usr/bin/env bash
# share-playground.sh — Compartir el PLAYGROUND del panel admin (chat con el LLM
# real) con otra maquina del tailnet de Tailscale.
#
# NO levanta servidores (para no pelear con el manejo de procesos en Windows):
# resuelve tu IP del tailnet y te deja los 2 comandos listos para pegar
# (backend + admin) con CORS, binds y URL ya rellenados, mas la URL que le
# mandas a tu amigo. Cada comando va en su propia terminal.
#
# Uso (desde la raiz del repo, en Git Bash):
#   bash scripts/share-playground.sh
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
  echo "ERROR: 'tailscale' no esta en el PATH de esta terminal."
  echo "  Instalar:  winget install tailscale.tailscale   (reabri la terminal despues)"
  echo "  Conectar:  tailscale up"
  exit 1
fi

IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
if [ -z "${IP}" ]; then
  echo "ERROR: Tailscale no esta conectado (no devolvio IP del tailnet)."
  echo "  Corre:  tailscale up"
  exit 1
fi

# CORS para el backend: localhost (test local) + el origin del tailnet (remoto).
CORS="http://localhost:3000,http://localhost:8081,http://localhost:3002,http://${IP}:3002,http://${IP}:3000"

cat <<EOF

  Tailnet IP de esta maquina: ${IP}

  --- Terminal 1 -- backend (serving real, escuchando en el tailnet) ---
  cd apps/backend && CORS_ORIGINS="${CORS}" uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

  --- Terminal 2 -- panel admin (mocks off, apuntando al backend del tailnet) ---
  NEXT_PUBLIC_API_URL="http://${IP}:8080" NEXT_PUBLIC_ENABLE_MOCKS=false pnpm --filter @ynara/admin dev -- -H 0.0.0.0

  --- Mandale esto a tu amigo ---
  http://${IP}:3002/playground     (que entre con tu cuenta admin)

  Checklist:
    * Tu cuenta debe ser admin: users.is_admin=true, o tu UUID en ADMIN_BOOTSTRAP_IDS (apps/backend/.env).
    * Ollama corriendo con los modelos (gemma4/qwen). LLM_BACKEND=vllm ya esta en tu .env.
    * Tu amigo tiene que estar en el MISMO tailnet (invitalo desde la consola de Tailscale).

EOF
