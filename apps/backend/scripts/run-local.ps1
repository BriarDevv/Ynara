# run-local.ps1 — levanta el backend contra la DB de DEV LOCAL (Windows).
#
# Atajo para que cambiar a dev sea UN comando: exporta un DATABASE_URL local
# (sin tocar tu .env) y arranca uvicorn con reload. El guard anti-prod
# (app/core/db_guard.py) no se dispara porque el host es localhost.
#
# Uso (desde apps/backend):
#   .\scripts\run-local.ps1                 # usa ynara_dev en :5433
#   $env:DEV_DATABASE_URL='...'; .\scripts\run-local.ps1   # override puntual
#
# Requiere un Postgres con pgvector escuchando en :5433 y la DB creada
# (ver "Base de datos: dev vs prod" en README.md).

$ErrorActionPreference = "Stop"

# DB de dev local por default; overridable con $env:DEV_DATABASE_URL.
$DevUrl = if ($env:DEV_DATABASE_URL) {
    $env:DEV_DATABASE_URL
} else {
    "postgresql://postgres:test@localhost:5433/ynara_dev"
}

$env:DATABASE_URL = $DevUrl
$env:ENVIRONMENT = "development"
# Cinturón y tiradores: garantizamos que NO haya un opt-in colgado de prod.
Remove-Item Env:YNARA_ALLOW_PROD_DB -ErrorAction SilentlyContinue

Write-Host "[run-local] DATABASE_URL -> $DevUrl" -ForegroundColor Green
Write-Host "[run-local] ENVIRONMENT  -> development" -ForegroundColor Green

# Preferimos el venv local; si no está, caemos a `uv run`.
$venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m uvicorn app.main:app --reload --port 8080
} else {
    uv run uvicorn app.main:app --reload --port 8080
}
