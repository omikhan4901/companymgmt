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
  uv run python -m scripts.check_migrations
  step "api: tests"
  uv run pytest -q
fi

if [ -f "$root/web/package.json" ]; then
  cd "$root/web"
  step "web: lint"
  npm run --silent lint
  step "web: types"
  npm run --silent typecheck
  step "web: unit tests"
  npm run --silent test
  step "web: build"
  npm run --silent build
fi

if [ -f "$root/site/package.json" ]; then
  cd "$root/site"
  step "site: build"
  npm run --silent build
fi

if command -v gitleaks >/dev/null 2>&1; then
  step "secrets scan"
  gitleaks detect --source "$root" --no-banner --redact
fi

printf '\n\033[1;32mAll checks passed.\033[0m\n'
