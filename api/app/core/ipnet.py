"""IP address checks: allowlists (CIDR) and "is this a public internet address"."""

from __future__ import annotations

import ipaddress

Address = ipaddress.IPv4Address | ipaddress.IPv6Address
MAX_ENTRIES = 50


def normalize(entries: list[str]) -> list[str]:
    """Clean CIDR entries ("203.0.113.7" becomes "203.0.113.7/32"). Raises ValueError
    naming the first entry that isn't a network."""
    out: list[str] = []
    if len(entries) > MAX_ENTRIES:
        raise ValueError(f"At most {MAX_ENTRIES} entries.")
    for entry in entries:
        try:
            network = ipaddress.ip_network(entry.strip(), strict=False)
        except ValueError as exc:
            raise ValueError(f"{entry!r} isn't an IP address or network.") from exc
        if str(network) not in out:
            out.append(str(network))
    return out


def parse(ip: str | None) -> Address | None:
    if not ip:
        return None
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def allowed(ip: str | None, entries: list[str]) -> bool:
    """Whether `ip` is inside one of the networks (an empty list allows everyone)."""
    if not entries:
        return True
    address = parse(ip)
    if address is None:
        return False
    for entry in entries:
        network = ipaddress.ip_network(entry, strict=False)
        if address.version == network.version and address in network:
            return True
    return False


def is_public(address: Address) -> bool:
    """A routable internet address: not private, loopback, link-local (cloud metadata),
    carrier-grade NAT, multicast, reserved or unspecified."""
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped or address.sixtofour
        if mapped is not None:
            return is_public(mapped)
        if address.teredo:
            return False
    return bool(address.is_global) and not address.is_multicast
