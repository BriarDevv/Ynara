# scripts/

Shells de utilidad. Ejecutables manuales — no se corren desde CI sin
revisión.

## Scripts

- `init.sh` — bootstrap inicial del proyecto (crea `.env` desde
  example, valida dependencias del sistema).
- `seed-db.sh` — siembra datos de prueba en la DB local (Supabase
  en MVP).
- `reset-memory.sh` — **DESTRUCTIVO**. Borra toda la memoria del
  usuario que se le indique. Pide confirmación.
- `export-user-data.sh` — exporta toda la memoria + sesiones de un
  usuario a JSON.
- `ynara-doctor.sh` — validaciones pre-PR (doctor 10/10); corre antes
  de abrir cualquier PR.

## Convención

- Bash con `set -euo pipefail`.
- Cualquier acción destructiva pide confirmación interactiva.
- Si es para producción, requiere confirmación humana doble (regla
  #1).
