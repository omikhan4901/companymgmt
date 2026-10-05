"""The public API contract: refuse breaking changes to /v1 (SCIM lives at /v1/scim/v2).

`docs/api/openapi-v1.json` is the published contract. `check` compares the running app
against it and lists anything that would break a client:

- an operation (method + path) removed,
- a response field removed, or its type changed,
- a request field that clients don't send today made required, or a type changed,
- an enum value removed from a response or a required query parameter added.

Adding things (new operations, optional fields, new response fields, enum values in
requests) is fine. After a deliberate, announced change (see docs/api/README.md), run
`accept` to update the snapshot.

    uv run python -m scripts.api_contract check
    uv run python -m scripts.api_contract accept
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SNAPSHOT = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-v1.json"
PUBLIC = ("/v1/",)
METHODS = ("get", "post", "put", "patch", "delete")
# Internal or app-only: not part of the promise to integrations.
PRIVATE = ("/v1/auth/", "/v1/operator/", "/v1/public/", "/v1/join", "/v1/sso/")


def current() -> dict[str, Any]:
    from app.main import app

    schema: dict[str, Any] = app.openapi()
    return schema


def _public(path: str) -> bool:
    return path.startswith(PUBLIC) and not path.startswith(PRIVATE)


def _resolve(schema: dict[str, Any], doc: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    if depth > 20:
        return schema
    ref = schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        return _resolve(doc["components"]["schemas"].get(name, {}), doc, depth + 1)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [_resolve(o, doc, depth + 1) for o in schema[key]]
            non_null = [o for o in options if o.get("type") != "null"]
            if len(non_null) == 1:
                return {**non_null[0], "nullable": len(non_null) != len(options)}
    return schema


def _kind(schema: dict[str, Any]) -> str:
    if "type" in schema:
        return str(schema["type"])
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            return key
    return "any"


def _compare_response(
    old: dict[str, Any],
    new: dict[str, Any],
    od: dict[str, Any],
    nd: dict[str, Any],
    where: str,
    out: list[str],
    depth: int = 0,
) -> None:
    if depth > 8:
        return
    o, n = _resolve(old, od), _resolve(new, nd)
    if _kind(o) != _kind(n) and "any" not in (_kind(o), _kind(n)):
        out.append(f"{where}: type changed from {_kind(o)} to {_kind(n)}")
        return
    if o.get("enum") and n.get("enum"):
        lost = set(map(str, o["enum"])) - set(map(str, n["enum"]))
        if lost:
            out.append(f"{where}: values removed: {sorted(lost)}")
    if _kind(o) == "object":
        for name, prop in (o.get("properties") or {}).items():
            if name not in (n.get("properties") or {}):
                out.append(f"{where}.{name}: removed from the response")
            else:
                _compare_response(prop, n["properties"][name], od, nd, f"{where}.{name}", out, depth + 1)
    if _kind(o) == "array" and "items" in o and "items" in n:
        _compare_response(o["items"], n["items"], od, nd, f"{where}[]", out, depth + 1)


def _compare_request(
    old: dict[str, Any],
    new: dict[str, Any],
    od: dict[str, Any],
    nd: dict[str, Any],
    where: str,
    out: list[str],
    depth: int = 0,
) -> None:
    if depth > 8:
        return
    o, n = _resolve(old, od), _resolve(new, nd)
    if _kind(o) != _kind(n) and "any" not in (_kind(o), _kind(n)):
        out.append(f"{where}: type changed from {_kind(o)} to {_kind(n)}")
        return
    if o.get("enum") and n.get("enum"):
        lost = set(map(str, o["enum"])) - set(map(str, n["enum"]))
        if lost:
            out.append(f"{where}: accepted values removed: {sorted(lost)}")
    if _kind(o) == "object":
        newly = set(n.get("required") or []) - set(o.get("required") or [])
        for name in sorted(newly):
            out.append(f"{where}.{name}: now required")
        for name, prop in (o.get("properties") or {}).items():
            if name in (n.get("properties") or {}):
                _compare_request(prop, n["properties"][name], od, nd, f"{where}.{name}", out, depth + 1)
            elif n.get("additionalProperties") is False:
                out.append(f"{where}.{name}: no longer accepted")


def _json_schema(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not body:
        return None
    content = body.get("content") or {}
    for media in ("application/json", "application/scim+json"):
        if media in content:
            schema: dict[str, Any] = content[media].get("schema") or {}
            return schema
    return None


def breaking(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for path, operations in old.get("paths", {}).items():
        if not _public(path):
            continue
        for method in METHODS:
            if method not in operations:
                continue
            where = f"{method.upper()} {path}"
            new_op = new.get("paths", {}).get(path, {}).get(method)
            if new_op is None:
                problems.append(f"{where}: removed")
                continue
            old_op = operations[method]
            old_params = {(p["in"], p["name"]): p for p in old_op.get("parameters", [])}
            for p in new_op.get("parameters", []):
                if p.get("required") and (p["in"], p["name"]) not in old_params:
                    problems.append(f"{where}: new required {p['in']} parameter {p['name']}")
            old_req, new_req = (
                _json_schema(old_op.get("requestBody")),
                _json_schema(new_op.get("requestBody")),
            )
            if old_req and new_req:
                _compare_request(old_req, new_req, old, new, f"{where} body", problems)
            elif new_req and not old_req and (new_op.get("requestBody") or {}).get("required"):
                problems.append(f"{where}: now needs a body")
            for status, response in (old_op.get("responses") or {}).items():
                if not status.startswith("2"):
                    continue
                new_response = (new_op.get("responses") or {}).get(status)
                if new_response is None:
                    problems.append(f"{where}: no longer answers {status}")
                    continue
                old_s, new_s = _json_schema(response), _json_schema(new_response)
                if old_s and new_s:
                    _compare_response(old_s, new_s, old, new, f"{where} → {status}", problems)
    return problems


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    schema = current()
    if command == "accept":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(schema, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"Contract updated: {SNAPSHOT}")
        return 0
    if not SNAPSHOT.exists():
        print("No contract yet; run `accept` once.")
        return 1
    problems = breaking(json.loads(SNAPSHOT.read_text()), schema)
    if problems:
        print("Breaking changes to the public API:")
        for p in problems:
            print(f"  - {p}")
        print("If this is deliberate, follow docs/api/README.md (deprecate first), then run `accept`.")
        return 1
    print("Public API: no breaking changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
