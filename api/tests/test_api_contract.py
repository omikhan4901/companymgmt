"""The public API contract check: it catches what breaks clients and allows additions."""

from __future__ import annotations

import copy
from typing import Any

from scripts import api_contract


def doc() -> dict[str, Any]:
    return {
        "paths": {
            "/v1/things": {
                "get": {
                    "parameters": [{"in": "query", "name": "q", "required": False}],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Thing"},
                                    }
                                }
                            }
                        }
                    },
                },
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ThingIn"}}}
                    },
                    "responses": {"201": {"content": {}}},
                },
            }
        },
        "components": {
            "schemas": {
                "Thing": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["a", "b"]},
                    },
                },
                "ThingIn": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}, "note": {"type": "string"}},
                },
            }
        },
    }


def test_additions_are_fine() -> None:
    old, new = doc(), doc()
    new["components"]["schemas"]["Thing"]["properties"]["extra"] = {"type": "integer"}
    new["paths"]["/v1/other"] = {"get": {"responses": {}}}
    new["components"]["schemas"]["Thing"]["properties"]["kind"]["enum"].append("c")
    assert api_contract.breaking(old, new) == []


def test_breaking_changes_are_caught() -> None:
    old = doc()
    removed_field = copy.deepcopy(old)
    del removed_field["components"]["schemas"]["Thing"]["properties"]["id"]
    assert any("id: removed" in p for p in api_contract.breaking(old, removed_field))

    required = copy.deepcopy(old)
    required["components"]["schemas"]["ThingIn"]["required"].append("note")
    assert any("note: now required" in p for p in api_contract.breaking(old, required))

    enum = copy.deepcopy(old)
    enum["components"]["schemas"]["Thing"]["properties"]["kind"]["enum"] = ["a"]
    assert any("values removed" in p for p in api_contract.breaking(old, enum))

    gone = copy.deepcopy(old)
    del gone["paths"]["/v1/things"]["post"]
    assert any("POST /v1/things: removed" in p for p in api_contract.breaking(old, gone))

    param = copy.deepcopy(old)
    param["paths"]["/v1/things"]["get"]["parameters"].append(
        {"in": "query", "name": "must", "required": True}
    )
    assert any("must" in p for p in api_contract.breaking(old, param))


def test_the_app_keeps_its_published_contract() -> None:
    import json

    published = json.loads(api_contract.SNAPSHOT.read_text())
    assert api_contract.breaking(published, api_contract.current()) == []
