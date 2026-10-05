import hashlib
import hmac

import httpx
import pytest

from companymgmt import CompanyMgmt, CompanyMgmtError, verify_webhook


def test_verify_webhook() -> None:
    body = b'{"id":"1"}'
    t = 1_700_000_000
    v1 = hmac.new(b"whsec_abc", f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_webhook("whsec_abc", body, f"t={t},v1={v1}", now=t + 5)
    assert not verify_webhook("whsec_abc", body + b" ", f"t={t},v1={v1}", now=t + 5)
    assert not verify_webhook("whsec_abc", body, f"t={t},v1={v1}", now=t + 1000)


def test_retries_reuse_the_idempotency_key_and_pagination() -> None:
    keys: list[str] = []
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/members"):
            cursor = request.url.params.get("cursor")
            if cursor is None:
                return httpx.Response(200, json={"items": [{"name": "A"}], "next_cursor": "c2"})
            return httpx.Response(200, json={"items": [{"name": "B"}], "next_cursor": None})
        calls["n"] += 1
        keys.append(request.headers["idempotency-key"])
        if calls["n"] == 1:
            return httpx.Response(503, headers={"retry-after": "0"})
        if calls["n"] == 2:
            return httpx.Response(201, json={"id": "b1"})
        return httpx.Response(422, json={"status": 422, "code": "validation"})

    cm = CompanyMgmt("cmk_x_y", transport=httpx.MockTransport(handler))
    assert [m["name"] for m in cm.paginate("/members")] == ["A", "B"]
    assert cm.post("/branches", {"name": "Uttara"}) == {"id": "b1"}
    assert keys[0] == keys[1]
    with pytest.raises(CompanyMgmtError) as error:
        cm.post("/branches", {})
    assert error.value.code == "validation"
