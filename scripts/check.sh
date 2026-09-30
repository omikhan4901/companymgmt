#!/usr/bin/env bash
# Runs every check that CI runs. Push to main only when this passes.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$1"; }

if [ -f "$root/api/pyproject.toml" ]; then
  cd "$root/api"
  step "api: lint and format"
  uv run ruff check .
  uv run ruff format --check .
  step "api: types"
  uv run mypy app
  step "api: module boundaries"
  uv run lint-imports
  step "api: migrations in sync with models"
  uv run alembic upgrade head >/dev/null
  uv run alembic check
  step "api: tests"
  uv run pytest -q
fi

if [ -f "$root/web/package.json" ]; then
  step "api contract: web types match the backend"
  "$root/scripts/gen-api-types.sh"
  git -C "$root" diff --exit-code -- web/src/api/openapi.json web/src/api/schema.d.ts
  cd "$root/web"
  step "web: lint"
  npm run --silent lint
  step "web: types"
  npm run --silent typecheck
  step "web: unit tests"
  npm run --silent test
  step "web: static build with per-page security headers"
  NEXT_TELEMETRY_DISABLED=1 npm run --silent build >/dev/null
  if [ "${E2E:-0}" = "1" ]; then
    step "web: end-to-end and accessibility (Playwright)"
    npx playwright test
  fi
fi

if command -v gitleaks >/dev/null 2>&1; then
  step "secrets scan"
  gitleaks detect --source "$root" --no-banner --redact
fi

printf '\n\033[1;32mAll checks passed.\033[0m\n'
