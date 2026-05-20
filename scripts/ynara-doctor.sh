#!/usr/bin/env bash
# Ynara doctor — validaciones pre-PR.
#
# Corre los chequeos mecánicos de las 10 reglas no negociables y de
# las landmines aprendidas. Exit 0 = todo OK. Exit 1 = al menos una
# falla — revisar antes de abrir o actualizar PR.
#
# Uso:
#   bash scripts/ynara-doctor.sh
#   make doctor

set -uo pipefail

# El script funciona desde cualquier path, normalizamos al root del repo
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
TOTAL_CHECKS=10

ok() {
  echo "  OK    $1"
  PASS=$((PASS + 1))
}

bad() {
  echo "  FAIL  $1"
  FAIL=$((FAIL + 1))
}

skip() {
  echo "  SKIP  $1"
}

header() {
  echo ""
  echo "[$1/$TOTAL_CHECKS] $2"
}

echo "==== Ynara doctor ===="
echo "Repo: $REPO_ROOT"

# ---------------------------------------------------------------------
# 1. .env.example presentes en root + cada app
# ---------------------------------------------------------------------
header 1 ".env.example presentes"
for f in .env.example apps/backend/.env.example apps/web/.env.example apps/mobile/.env.example; do
  if [ -f "$f" ]; then
    ok "$f"
  else
    bad "$f no existe"
  fi
done

# ---------------------------------------------------------------------
# 2. Ningún .env real commiteado (regla #2)
# ---------------------------------------------------------------------
header 2 "Ningún .env real commiteado (regla #2)"
leaked=$(git ls-files 2>/dev/null \
  | grep -E '(^|/)\.env(\.local|\.development|\.production|\.test)?$' \
  | grep -v '\.example$' || true)
if [ -n "$leaked" ]; then
  bad "archivos .env trackeados (deberían estar gitignored)"
  echo "$leaked" | sed 's/^/        /'
else
  ok "ningún .env real trackeado"
fi

# ---------------------------------------------------------------------
# 3. Sin cliente Supabase en frontend (regla #5)
# ---------------------------------------------------------------------
header 3 "Sin @supabase/supabase-js en frontend (regla #5)"
supabase_hits=$(grep -rn --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='package.json' \
  '@supabase/supabase-js' apps/web apps/mobile packages 2>/dev/null \
  | grep -v node_modules || true)
if [ -n "$supabase_hits" ]; then
  bad "referencia a @supabase/supabase-js encontrada"
  echo "$supabase_hits" | sed 's/^/        /'
else
  ok "ningún import o dep de @supabase/supabase-js"
fi

# ---------------------------------------------------------------------
# 4. Sin APIs externas de IA en backend (regla #4)
# ---------------------------------------------------------------------
header 4 "Sin APIs externas de IA en backend (regla #4)"
ai_apis=$(grep -rn --include='*.py' \
  -E '^(import|from) (openai|anthropic|google\.generativeai|cohere|mistralai)' \
  apps/backend/app 2>/dev/null || true)
if [ -n "$ai_apis" ]; then
  bad "import de API externa de IA detectado"
  echo "$ai_apis" | sed 's/^/        /'
else
  ok "ningún import de openai/anthropic/google.generativeai/cohere/mistralai"
fi

# ---------------------------------------------------------------------
# 5. ynara.config.json parseable
# ---------------------------------------------------------------------
header 5 "ynara.config.json parseable"
if [ ! -f ynara.config.json ]; then
  bad "ynara.config.json no existe"
elif command -v python3 >/dev/null 2>&1 \
  && python3 -c "import json,sys; json.load(open('ynara.config.json'))" 2>/dev/null; then
  ok "JSON válido (parseado con python3)"
elif command -v node >/dev/null 2>&1 \
  && node -e "JSON.parse(require('fs').readFileSync('ynara.config.json','utf8'))" 2>/dev/null; then
  ok "JSON válido (parseado con node)"
else
  bad "no se pudo parsear (falta python3/node o JSON inválido)"
fi

# ---------------------------------------------------------------------
# 6. Adapters CLAUDE/CODEX/GEMINI referencian AGENTS.md
# ---------------------------------------------------------------------
header 6 "Adapters apuntan a AGENTS.md"
for f in CLAUDE.md CODEX.md GEMINI.md; do
  if [ ! -f "$f" ]; then
    bad "$f no existe"
  elif grep -q "AGENTS.md" "$f"; then
    ok "$f referencia AGENTS.md"
  else
    bad "$f no referencia AGENTS.md (golden rule rota)"
  fi
done

# ---------------------------------------------------------------------
# 7. Tablas sagradas en el PR — solo informativo (regla #3)
# ---------------------------------------------------------------------
header 7 "Tablas sagradas en el PR (regla #3)"
sagrado_changes=""
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  base_ref=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo "")
  if [ -n "$base_ref" ]; then
    sagrado_changes=$(git diff --name-only "$base_ref"..HEAD 2>/dev/null \
      | grep -E '^(apps/backend/app/memory/|apps/backend/alembic/versions/|apps/backend/app/models/(memory|audit)\.py|apps/backend/app/schemas/(memory|audit)\.py)' || true)
  fi
fi
if [ -n "$sagrado_changes" ]; then
  bad "el PR toca tablas sagradas — requiere tests + 1 aprobación humana explícita (regla #3)"
  echo "$sagrado_changes" | sed 's/^/        /'
else
  ok "PR no toca tablas sagradas (o no se pudo comparar con main)"
fi

# ---------------------------------------------------------------------
# 8. Lockfiles trackeados si existen
# ---------------------------------------------------------------------
header 8 "Lockfiles trackeados si existen"
for f in pnpm-lock.yaml apps/backend/uv.lock; do
  if [ -f "$f" ]; then
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      ok "$f trackeado"
    else
      bad "$f existe pero no está trackeado"
    fi
  else
    skip "$f todavía no existe (esperado en pre-install)"
  fi
done

# ---------------------------------------------------------------------
# 9. Sin tailwind.config.ts en apps/web (Tailwind v4 es CSS-first)
# ---------------------------------------------------------------------
header 9 "Tailwind v4 — sin tailwind.config.ts en apps/web"
if [ -f apps/web/tailwind.config.ts ] || [ -f apps/web/tailwind.config.js ]; then
  bad "apps/web tiene tailwind.config — Tailwind v4 es CSS-first, los tokens van en globals.css con @theme"
else
  ok "ningún tailwind.config en apps/web"
fi

# ---------------------------------------------------------------------
# 10. Rama actual deriva del tip de origin/main (landmine: PR #13 incident)
# ---------------------------------------------------------------------
header 10 "Rama actual deriva del tip de origin/main"
current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")
if [ "$current_branch" = "main" ]; then
  skip "estás en main — no aplica"
elif [ "$current_branch" = "DETACHED" ]; then
  skip "HEAD detached — no aplica"
else
  origin_main_sha=$(git rev-parse origin/main 2>/dev/null || echo "")
  merge_base_sha=$(git merge-base HEAD origin/main 2>/dev/null || echo "")
  if [ -z "$origin_main_sha" ]; then
    skip "no se pudo leer origin/main (no fetch reciente?)"
  elif [ -z "$merge_base_sha" ]; then
    skip "no se pudo calcular merge-base con origin/main"
  elif [ "$merge_base_sha" = "$origin_main_sha" ]; then
    ok "rama '$current_branch' deriva del tip de origin/main"
  else
    bad "rama '$current_branch' diverge de origin/main"
    echo "        merge-base con origin/main: $merge_base_sha"
    echo "        origin/main tip:            $origin_main_sha"
    echo "        Si la rama deriva del tip de un PR ajeno, el merge fast-forward"
    echo "        puede arrastrar esos commits a main por inercia (caso PR #13)."
    echo "        Fix: git fetch origin && git rebase origin/main"
  fi
fi

# ---------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------
echo ""
echo "==== Resumen ===="
echo "  Pasaron:  $PASS"
echo "  Fallaron: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "Ynara doctor: $FAIL falla(s). Revisar antes de PR."
  exit 1
fi

echo "Ynara doctor: OK."
exit 0
