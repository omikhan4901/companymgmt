#!/usr/bin/env bash
# Regenerates the web app's typed API client from the backend's OpenAPI schema.
# check.sh fails if the committed copy is out of date.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/web/src/api"
(cd "$root/api" && ENV=test uv run python -c "
import json
from app.main import app
print(json.dumps(app.openapi(), indent=1, sort_keys=True, ensure_ascii=False))
") > "$root/web/src/api/openapi.json"
(cd "$root/web" && npx openapi-typescript src/api/openapi.json -o src/api/schema.d.ts >/dev/null)
# The Next.js app that replaces web/ (M1.6) keeps its own copy until the switch.
if [ -d "$root/web-next/src/api" ]; then
  cp "$root/web/src/api/openapi.json" "$root/web/src/api/schema.d.ts" "$root/web-next/src/api/"
fi
