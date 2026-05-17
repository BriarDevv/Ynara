#!/usr/bin/env bash
# DESTRUCTIVO: borra toda la memoria de un usuario.
# Pide confirmación interactiva. En CI o producción, refusa correr.

set -euo pipefail

if [ "${CI:-}" = "true" ]; then
  echo "[reset-memory] PROHIBIDO en CI."
  exit 1
fi

if [ "${ENVIRONMENT:-development}" = "production" ]; then
  echo "[reset-memory] PROHIBIDO en production sin doble OK humano."
  echo "[reset-memory] Si realmente querés, ejecutá manualmente desde la VPS con dos pares de ojos."
  exit 1
fi

USER_ID="${1:-}"
if [ -z "$USER_ID" ]; then
  echo "uso: $0 <user_id>"
  exit 1
fi

echo "Vas a BORRAR TODA la memoria del usuario: $USER_ID"
read -r -p "Escribí EXACTAMENTE 'borrar' para confirmar: " confirm
if [ "$confirm" != "borrar" ]; then
  echo "[reset-memory] abortado."
  exit 1
fi

# TODO: implementar con psql + DELETEs explícitos. Acá queda el
# placeholder.
echo "[reset-memory] TODO: implementar query SQL. No corrió nada."
