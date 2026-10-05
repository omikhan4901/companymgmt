"""Outbound HTTPS to addresses people type in (webhooks, sign-in providers), safely.

Only https, only public internet addresses. The name is resolved and every address it
points to is checked right before each request, and the connection goes to the checked
address (the name rides in the Host header and TLS SNI), so DNS tricks can't point us at
internal services or cloud metadata. Redirects are never followed.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core import ipnet

MAX_URL = 500
TIMEOUT_SECONDS = 10
PORTS = (None, 443, 8443)
MAX_BODY = 1_000_000

# Tests swap in an httpx.MockTransport.
transport: httpx.AsyncBaseTransport | None = None


class UnsafeAddress(ValueError):
    pass


def check_url(url: str) -> str:
    """The URL, tidied, if it's an acceptable address (shape only; DNS is checked when
    sending). Raises UnsafeAddress with a reason people can act on."""
    url = url.strip()
    if len(url) > MAX_URL:
        raise UnsafeAddress("The address is too long.")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise UnsafeAddress("Use an https:// address.")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeAddress("The port isn't valid.") from exc
    if not parts.hostname or parts.username or parts.password:
        raise UnsafeAddress("Use an address like https://example.com/hooks, without a username or password.")
    if port not in PORTS:
        raise UnsafeAddress("Use the standard https port (443 or 8443).")
    host = parts.hostname.rstrip(".").lower()
    literal = ipnet.parse(host)
    if literal is not None and not ipnet.is_public(literal):
        raise UnsafeAddress("Only public internet addresses can be used.")
    if literal is None and ("." not in host or host.endswith((".local", ".internal", ".localhost", ".lan"))):
        raise UnsafeAddress("Only public internet addresses can be used.")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", parts.query, ""))


async def resolve(host: str, port: int) -> list[str]:
    """Every address the name points to (tests replace this)."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


async def pinned_target(url: str) -> tuple[str, str]:
    """(URL with the host replaced by a checked public IP, the original host name)."""
    url = check_url(url)
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or 443
    literal = ipnet.parse(host)
    addresses = [host] if literal is not None else await resolve(host, port)
    if not addresses:
        raise UnsafeAddress("The address doesn't resolve.")
    for address in addresses:
        parsed = ipnet.parse(address)
        if parsed is None or not ipnet.is_public(parsed):
            raise UnsafeAddress("The address points to a private network.")
    chosen = ipaddress.ip_address(addresses[0])
    netloc = f"[{chosen}]" if chosen.version == 6 else str(chosen)
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, "")), host


async def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    """One request to a checked, pinned address. Raises UnsafeAddress or httpx errors."""
    target, host = await pinned_target(url)
    headers = {**kwargs.pop("headers", {}), "Host": host}
    async with httpx.AsyncClient(
        transport=transport, timeout=TIMEOUT_SECONDS, follow_redirects=False
    ) as client:
        return await client.request(
            method, target, headers=headers, extensions={"sni_hostname": host}, **kwargs
        )


async def get_json(url: str) -> Any:
    """GET a JSON document (sign-in provider metadata and keys)."""
    response = await request("GET", url, headers={"Accept": "application/json"})
    if response.status_code != 200:
        raise UnsafeAddress(f"The address answered {response.status_code}.")
    if len(response.content) > MAX_BODY:
        raise UnsafeAddress("The answer is too large.")
    return response.json()
