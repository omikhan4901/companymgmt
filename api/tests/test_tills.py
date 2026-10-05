"""Shared tills: a registered device plus a cashier's PIN opens a selling-only session."""

from __future__ import annotations

from typing import Any

import httpx

from tests.helpers import Account, add_staff, signup

WEB = {"x-cm-client": "web"}


async def set_up(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client, business_type="shop")
    till = await owner.post("/v1/sales/tills", json={"name": "Front counter"})
    assert till.status_code == 201, till.text
    member, cashier = await add_staff(owner, name="Rina", role="cashier")
    pin = await cashier.put("/v1/sales/my-pin", json={"pin": "4826"})
    assert pin.status_code == 200, pin.text
    return {"owner": owner, "till": till.json(), "member": member["member"], "cashier": cashier}


def till_headers(token: str) -> dict[str, str]:
    return {**WEB, "x-till-token": token}


async def unlock(client: httpx.AsyncClient, token: str, member_id: str, pin: str) -> httpx.Response:
    return await client.post(
        "/v1/till/unlock", json={"membership_id": member_id, "pin": pin}, headers=till_headers(token)
    )


async def test_pin_unlocks_a_selling_only_session(client: httpx.AsyncClient) -> None:
    s = await set_up(client)
    token = s["till"]["token"]
    info = await client.get("/v1/till", headers=till_headers(token))
    assert [c["name"] for c in info.json()["cashiers"]] == ["Rina"]

    opened = await unlock(client, token, s["member"]["id"], "4826")
    assert opened.status_code == 200, opened.text
    access = {"Authorization": f"Bearer {opened.json()['access_token']}"}
    me = (await client.get("/v1/auth/me", headers=access)).json()
    assert set(me["workspace"]["permissions"]) <= {
        "sales.sell",
        "customers.view",
        "customers.manage",
        "expenses.record",
    }
    # Can't change the account from a till.
    changed = await client.post(
        "/v1/auth/password/change", json={"current_password": "x", "new_password": "y" * 12}, headers=access
    )
    assert (changed.status_code, changed.json()["code"]) == (403, "till_session")

    # Revoking the till ends the session at once.
    assert (await s["owner"].delete(f"/v1/sales/tills/{s['till']['id']}")).status_code == 204
    assert (await client.get("/v1/auth/me", headers=access)).status_code == 401
    assert (await client.get("/v1/till", headers=till_headers(token))).status_code == 401


async def test_wrong_pins_lock_and_pins_need_a_till(client: httpx.AsyncClient) -> None:
    s = await set_up(client)
    token = s["till"]["token"]
    assert (await unlock(client, "till_nope_x", s["member"]["id"], "4826")).status_code == 401
    for _ in range(5):
        assert (await unlock(client, token, s["member"]["id"], "1357")).status_code == 401
    locked = await unlock(client, token, s["member"]["id"], "4826")
    assert (locked.status_code, locked.json()["code"]) == (429, "pin_locked")


async def test_weak_pins_are_refused(client: httpx.AsyncClient) -> None:
    owner: Account = await signup(client, business_type="shop")
    for pin in ("1111", "1234", "9876"):
        assert (await owner.put("/v1/sales/my-pin", json={"pin": pin})).status_code == 422
    assert (await owner.put("/v1/sales/my-pin", json={"pin": "12a4"})).status_code == 422
