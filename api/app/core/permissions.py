"""Permission catalog. Each module registers the permissions it checks.

A permission is a string such as `people.manage`. Roles are sets of permissions. Some
permissions can be limited to a department subtree (`scoped=True`), for example a manager
who sees only their own department.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    key: str
    module: str
    label: str
    scoped: bool = False
    # Only owners may hold it; it can't be put in a custom role.
    owner_only: bool = False


_REGISTRY: dict[str, Permission] = {}


def register(key: str, label: str, *, module: str, scoped: bool = False, owner_only: bool = False) -> str:
    existing = _REGISTRY.get(key)
    perm = Permission(key, module, label, scoped, owner_only)
    if existing and existing != perm:
        raise ValueError(f"Permission {key} registered twice with different settings.")
    _REGISTRY[key] = perm
    return key


def get(key: str) -> Permission:
    return _REGISTRY[key]


def exists(key: str) -> bool:
    return key in _REGISTRY


def catalog() -> list[Permission]:
    return sorted(_REGISTRY.values(), key=lambda p: (p.module, p.key))
