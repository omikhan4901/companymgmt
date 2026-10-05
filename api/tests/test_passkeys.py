"""Passkeys with a software authenticator: register, sign in without a password, and the
checks that matter (challenge reuse, wrong origin, cloned keys)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from typing import Any

import cbor2
import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import get_settings
from app.modules.platform.passkeys import relying_party
from tests.helpers import Account, signup

WEB = {"x-cm-client": "web"}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Authenticator:
    """A phone or password manager, in software."""

    def __init__(self, origin: str | None = None) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.count = 0
        self.origin = origin or get_settings().web_base_url.rstrip("/")
        self.rp_hash = hashlib.sha256(relying_party()[0].encode()).digest()

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False}
        ).encode()

    def create(self, options: dict[str, Any]) -> dict[str, Any]:
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")}
        )
        attested = bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id + cose
        auth_data = self.rp_hash + bytes([0x45]) + struct.pack(">I", self.count) + attested
        client_data = self._client_data("webauthn.create", options["challenge"])
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "attestationObject": b64(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def get(self, options: dict[str, Any], *, count: int | None = None) -> dict[str, Any]:
        self.count = self.count + 1 if count is None else count
        auth_data = self.rp_hash + bytes([0x05]) + struct.pack(">I", self.count)
        client_data = self._client_data("webauthn.get", options["challenge"])
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
            },
            "clientExtensionResults": {},
        }


async def register(owner: Account, device: Authenticator) -> httpx.Response:
    options = (await owner.post("/v1/auth/passkeys/register/options")).json()
    return await owner.post(
        "/v1/auth/passkeys/register",
        json={
            "challenge_id": options["challenge_id"],
            "credential": device.create(options["options"]),
            "name": "Phone",
        },
    )


async def sign_in(client: httpx.AsyncClient, device: Authenticator, **kw: Any) -> httpx.Response:
    options = (await client.post("/v1/auth/passkeys/login/options")).json()
    return await client.post(
        "/v1/auth/passkeys/login",
        json={"challenge_id": options["challenge_id"], "credential": device.get(options["options"], **kw)},
        headers=WEB,
    )


async def test_register_and_sign_in_without_a_password(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    device = Authenticator()
    made = await register(owner, device)
    assert made.status_code == 201, made.text
    assert [p["name"] for p in (await owner.get("/v1/auth/passkeys")).json()] == ["Phone"]

    signed = await sign_in(client, device)
    assert signed.status_code == 200, signed.text
    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {signed.json()['access_token']}"})
    assert me.json()["email"] == owner.email


async def test_bad_answers_are_refused(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    device = Authenticator()
    assert (await register(owner, device)).status_code == 201

    # A challenge works once.
    options = (await client.post("/v1/auth/passkeys/login/options")).json()
    body = {"challenge_id": options["challenge_id"], "credential": device.get(options["options"])}
    assert (await client.post("/v1/auth/passkeys/login", json=body, headers=WEB)).status_code == 200
    assert (await client.post("/v1/auth/passkeys/login", json=body, headers=WEB)).status_code == 401

    # Another site's page can't use it.
    phish = Authenticator(origin="https://companymgmt-login.example")
    phish.key, phish.credential_id, phish.count = device.key, device.credential_id, device.count
    assert (await sign_in(client, phish)).status_code == 401

    # A cloned key shows up as a counter going backwards.
    assert (await sign_in(client, device, count=1)).status_code == 401

    # Unknown keys are refused.
    assert (await sign_in(client, Authenticator())).status_code == 401
