#!/usr/bin/env bash
# Exporta toda la memoria + sesiones de un usuario a JSON.
# El JSON se guarda en exports/<user_id>-<timestamp>.json (gitignored).

set -euo pipefail

USER_ID="${1:-}"
if [ -z "$USER_ID" ]; then
  echo "uso: $0 <user_id>"
  exit 1
fi

mkdir -p exports
OUT="exports/${USER_ID}-$(date +%Y%m%d-%H%M%S).json"

# TODO: implementar. Idea: llamar al endpoint /v1/memory/export con
# token de admin, o ejecutar query SQL directa contra la DB de
# producción (con doble OK humano).

echo "[export-user-data] TODO: implementar."
echo "[export-user-data] target: $OUT"
exit 1
