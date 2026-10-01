"""The capability registry: every action the product can take, described for machines.

Each module registers typed functions (`people.search`, `leave.balances`, …) with their
input and output schemas, the permission and module they need, and whether they only
read or also change data. The REST routes call the same service functions, and later the
AI layer (M6) picks capabilities as tools: it gets these, never the database.

Invoking a capability runs `check_access` (exactly what the REST dependency runs) and
then the function with the caller's own context, so department scope, row-level security
and plan limits apply the same way.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.core.errors import Invalid, NotFound
from app.modules.platform.deps import Ctx, check_access

Kind = Literal["read", "write"]


@dataclass(frozen=True)
class Capability:
    name: str
    summary: str
    module: str | None
    permission: str | None
    kind: Kind
    input: type[BaseModel]
    output: Any
    run: Callable[[Ctx, Any], Awaitable[Any]]
    # Results are limited to the caller's department subtree for scoped roles.
    scoped: bool = False
    # The REST route with the same meaning, e.g. "GET /v1/leave/balances/team".
    route: str | None = None
    adapter: TypeAdapter[Any] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter", TypeAdapter(self.output))

    def visible_to(self, ctx: Ctx) -> bool:
        entitlements = ctx.entitlements
        if self.module is not None and (entitlements is None or self.module not in entitlements.modules):
            return False
        return self.permission is None or ctx.can(self.permission)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "kind": self.kind,
            "module": self.module,
            "permission": self.permission,
            "scoped": self.scoped,
            "route": self.route,
            "input_schema": self.input.model_json_schema(),
            "output_schema": self.adapter.json_schema(),
        }


REGISTRY: dict[str, Capability] = {}


class NoInput(BaseModel):
    """For capabilities that take nothing."""


def capability(
    name: str,
    summary: str,
    *,
    input: type[BaseModel] = NoInput,
    output: Any,
    permission: str | None,
    module: str | None,
    kind: Kind = "read",
    scoped: bool = False,
    route: str | None = None,
) -> Callable[[Callable[[Ctx, Any], Awaitable[Any]]], Callable[[Ctx, Any], Awaitable[Any]]]:
    def register(fn: Callable[[Ctx, Any], Awaitable[Any]]) -> Callable[[Ctx, Any], Awaitable[Any]]:
        if name in REGISTRY and REGISTRY[name].run is not fn:
            raise ValueError(f"Capability {name} is registered twice.")
        REGISTRY[name] = Capability(
            name=name,
            summary=summary,
            module=module,
            permission=permission,
            kind=kind,
            input=input,
            output=output,
            run=fn,
            scoped=scoped,
            route=route,
        )
        return fn

    return register


async def invoke(
    ctx: Ctx, name: str, payload: dict[str, Any] | None = None, *, allow_writes: bool = False
) -> Any:
    """Run a capability as the caller and return JSON-ready output."""
    cap = REGISTRY.get(name)
    if cap is None:
        raise NotFound(f"No capability called {name}.")
    if cap.kind == "write" and not allow_writes:
        # Changes go through propose → confirm (M7); until then only reads run here.
        raise Invalid("This capability changes data and needs confirmation.", code="write_needs_confirmation")
    check_access(ctx, cap.permission, module=cap.module, writing=cap.kind == "write")
    try:
        data = cap.input.model_validate(payload or {})
    except ValidationError as exc:
        errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        raise Invalid(errors=errors) from exc
    result = await cap.run(ctx, data)
    return cap.adapter.dump_python(result, mode="json")


def visible(ctx: Ctx) -> list[Capability]:
    return [c for c in sorted(REGISTRY.values(), key=lambda c: c.name) if c.visible_to(ctx)]
