"""Test helpers: sign up workspaces, add members, read emails."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core import email

PASSWORD = "correct horse battery staple 42"
WEB = {"x-cm-client": "web", "origin": "https://app.test"}


@dataclass
class Account:
    client: httpx.AsyncClient
    token: str
    email: str | None
    password: str
    refresh: str | None
    me: dict[str, Any] = field(default_factory=dict)

    @property
    def headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    @property
    def tenant_id(self) -> str:
        return str(self.me["workspace"]["id"])

    @property
    def membership_id(self) -> str:
        return str(self.me["workspace"]["membership_id"])

    async def get(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.get(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    async def post(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.post(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    async def patch(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.patch(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    async def put(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.put(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    async def delete(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.delete(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    async def reload(self) -> dict[str, Any]:
        response = await self.get("/v1/auth/me")
        assert response.status_code == 200, response.text
        self.me = response.json()
        return self.me


def cookie(refresh: str) -> dict[str, str]:
    return {"cookie": f"cm_refresh={refresh}"}


def refresh_cookie(response: httpx.Response) -> str | None:
    for header in response.headers.get_list("set-cookie"):
        match = re.match(r"cm_refresh=([^;]*);", header)
        if match:
            return match.group(1) or None
    return None


async def signup(
    client: httpx.AsyncClient,
    *,
    email_addr: str | None = None,
    name: str = "Rahim Uddin",
    business: str = "Cha Ghor",
    business_type: str = "office",
    timezone: str = "Asia/Dhaka",
    country: str | None = "BD",
    password: str = PASSWORD,
) -> Account:
    email_addr = email_addr or f"owner-{secrets.token_hex(4)}@example.com"
    response = await client.post(
        "/v1/auth/signup",
        json={
            "name": name,
            "email": email_addr,
            "password": password,
            "business_name": business,
            "business_type": business_type,
            "timezone": timezone,
            "country": country,
        },
    )
    assert response.status_code == 201, response.text
    account = Account(client, response.json()["access_token"], email_addr, password, refresh_cookie(response))
    await account.reload()
    return account


async def login(client: httpx.AsyncClient, email_addr: str, password: str = PASSWORD) -> Account:
    response = await client.post("/v1/auth/login", json={"email": email_addr, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    account = Account(client, body["access_token"], email_addr, password, refresh_cookie(response))
    await account.reload()
    return account


async def role_id(account: Account, key: str) -> str:
    roles = (await account.get("/v1/roles")).json()
    return next(r["id"] for r in roles if r["key"] == key)


async def add_staff(
    owner: Account, *, name: str = "Karim", username: str | None = None, role: str = "employee", **extra: Any
) -> tuple[dict[str, Any], Account]:
    """Create a staff account and sign in as it (password already changed)."""
    username = username or f"staff{secrets.token_hex(3)}"
    body = {"name": name, "username": username, "role_id": await role_id(owner, role), **extra}
    response = await owner.post("/v1/members/staff", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    login_response = await owner.client.post(
        "/v1/auth/login",
        json={
            "workspace": data["workspace_code"],
            "username": username,
            "password": data["temporary_password"],
        },
    )
    assert login_response.status_code == 200, login_response.text
    staff = Account(
        owner.client, login_response.json()["access_token"], None, data["temporary_password"], None
    )
    change = await staff.post(
        "/v1/auth/password/change",
        json={"current_password": data["temporary_password"], "new_password": PASSWORD + "!"},
    )
    assert change.status_code == 204, change.text
    staff.password = PASSWORD + "!"
    await staff.reload()
    return data, staff


def last_email(to: str) -> email.Mail:
    mails = [m for m in email.sent if m.to == to]
    assert mails, f"No email to {to}"
    return mails[-1]


def link_token(mail: email.Mail) -> str:
    match = re.search(r"token=([A-Za-z0-9_\-.]+)", mail.text)
    assert match, mail.text
    return match.group(1)


async def invite_and_join(owner: Account, role: str = "employee", **extra: Any) -> Account:
    """Invite a brand-new person by email and accept as them."""
    await verify_email(owner)
    addr = f"member-{secrets.token_hex(4)}@example.com"
    response = await owner.post(
        "/v1/invites", json={"email": addr, "role_id": await role_id(owner, role), **extra}
    )
    assert response.status_code == 201, response.text
    token = link_token(last_email(addr))
    accept = await owner.client.post(
        "/v1/invites/accept", json={"token": token, "name": "Member Person", "password": PASSWORD}
    )
    assert accept.status_code == 200, accept.text
    member = Account(owner.client, accept.json()["access_token"], addr, PASSWORD, refresh_cookie(accept))
    await member.reload()
    return member


async def verify_email(account: Account) -> None:
    if account.me.get("email_verified"):
        return
    assert account.email
    token = link_token([m for m in email.sent if m.to == account.email and "Confirm" in m.subject][-1])
    response = await account.client.post("/v1/auth/email/verify", json={"token": token})
    assert response.status_code == 204, response.text
    await account.reload()


def if_match(version: int) -> dict[str, str]:
    return {"if-match": f'W/"{version}"'}
