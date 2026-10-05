# 12. Adding a feature

Two walkthroughs: a small change to an existing module, then a whole new module, end to
end, written the way the rest of the code is. Neither exists in the code yet; type them out
as practice.

## 12.1 The checklist (for any change)

1. **Model** and **migration** (with RLS for new tenant tables).
2. **Schemas** with length limits.
3. **Permission** (if new) and who gets it by default.
4. **Service** with the rules; audit and event if it matters.
5. **Routes** declaring their access; ETag for versioned rows.
6. **Capability** if the AI should be able to read or propose it.
7. **Webhook** catalogue entry if customers' systems should hear about it.
8. **Tests**: the rule, the scope (404 for others), the permission (403), the plan (402).
9. `scripts/gen-api-types.sh`; `uv run python -m scripts.api_contract accept` if you
   *added* to the public API (never to hide a breaking change).
10. **Screen**, **nav item**, **texts in English and Bangla**.
11. **Browser journey** if people would notice it breaking.
12. **Docs**: a line in `docs/PROGRESS.md`; the help article if users need it; the README if
    it's a selling point; `docs/api/README.md` if it's public API.
13. `E2E=1 scripts/check.sh` → commit (`feat(<module>): …`) → push → deploy.

## 12.2 Small: a note on holidays

"Office closed, deliveries continue."

1. `api/app/modules/leave/models.py`, class `Holiday`:
   ```python
   note: Mapped[str | None] = mapped_column(String(500))
   ```
2. Migration:
   ```bash
   cd api && uv run alembic revision --autogenerate -m "holiday note"
   ```
   Rename to `…_0030_holiday_note.py`, set `revision = "0030"`, `down_revision = "0029"`.
   Autogenerate writes `op.add_column("holidays", sa.Column("note", sa.String(500), nullable=True))`.
   `uv run alembic upgrade head && uv run alembic check`.
3. `leave/schemas.py`: `note: Note | None = None` in `HolidayIn`; `note: str | None` in
   `HolidayOut` (`Note` comes from `app.core.schema`: cleaned, ≤500).
4. `leave/service.py`, where holidays are added: `note=body.note`, and include it in the
   audit data.
5. Test in `tests/test_leave.py`:
   ```python
   async def test_holidays_keep_a_note(client):
       owner = await signup(client)
       r = await owner.post("/v1/leave/holidays", json={"day": "2026-12-16", "name": "Victory Day",
                                                       "note": "Deliveries continue"})
       assert r.status_code == 201 and r.json()["note"] == "Deliveries continue"
       r = await owner.post("/v1/leave/holidays", json={"day": "2026-12-17", "name": "X", "note": "x" * 501})
       assert r.status_code == 422
   ```
6. `scripts/gen-api-types.sh`.
7. The holiday form (find it: `grep -rn "leave/holidays" web/src`): a `Field` with an
   `Input` bound to `note`; show the note under the holiday's name in the list.
8. `en.ts`: `holidayNote: "Note"`; `bn.ts`: `holidayNote: "নোট"`.
9. `E2E=1 scripts/check.sh`, commit `feat(leave): a note on holidays`, push.

## 12.3 Big: a new module, "Assets" (company equipment lent to people)

What it does: record laptops, phones and tools; lend them to a person; see who has what;
get them back. Managers handle their departments' assets; everyone sees what they hold.

### 1. Register the module and its permissions

`api/app/modules/platform/catalog.py`, in `MODULES`:

```python
Module("assets", "Assets", requires=("people",)),
```

`api/app/modules/assets/__init__.py` (empty) and `access.py`:

```python
"""Asset permissions."""
from app.core import permissions as perms

VIEW = perms.register("assets.view", "See assets and who holds them", module="assets", scoped=True)
MANAGE = perms.register("assets.manage", "Add assets, lend them and take them back",
                        module="assets", scoped=True)
```

Give the manager role both in `BUILTIN_ROLES` (`"assets.view", "assets.manage"`). Owners and
admins get everything automatically. Optionally add `"assets"` to the `office` and
`factory` presets in `BUSINESS_TYPES`.

### 2. Model

`api/app/modules/assets/models.py`:

```python
"""Company assets and who holds them."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class Asset(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "tag"),
        CheckConstraint("status IN ('available', 'lent', 'retired')", name="status"),
        ForeignKeyConstraint(["tenant_id", "holder_id"], ["employees.tenant_id", "employees.id"]),
        ForeignKeyConstraint(["tenant_id", "department_id"], ["departments.tenant_id", "departments.id"]),
    )

    tag: Mapped[str] = mapped_column(String(40))              # "LAP-014"
    name: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[uuid.UUID | None]                   # who looks after it (scope)
    status: Mapped[str] = mapped_column(String(10), default="available")
    holder_id: Mapped[uuid.UUID | None]                       # an employee
    lent_at: Mapped[datetime | None]
```

Import it in `api/app/models_registry.py`:
`from app.modules.assets import models as _assets  # noqa: F401`.

### 3. Migration

```bash
cd api && uv run alembic revision --autogenerate -m "assets"
```

Rename to `…_0030_assets.py`, set the revision ids, and after `op.create_table("assets", …)`:

```python
from migrations import rls
...
    rls.tenant_table("assets")
```

and in `downgrade()`, `op.drop_table("assets")` (the policy goes with it). Then
`uv run alembic upgrade head && uv run alembic check`.

### 4. Schemas

`assets/schemas.py`:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import Field
from app.core.schema import In, Name, Out


class AssetIn(In):
    tag: str = Field(min_length=1, max_length=40)
    name: Name
    department_id: uuid.UUID | None = None


class LendIn(In):
    employee_id: uuid.UUID


class AssetOut(Out):
    id: uuid.UUID
    tag: str
    name: str
    department_id: uuid.UUID | None
    status: str
    holder_id: uuid.UUID | None
    lent_at: datetime | None
    version: int
```

Names must be unique across the whole API (a test checks): `AssetIn`, `AssetOut`, and
`LendIn` are fine; if `LendIn` already existed you'd call it `AssetLendIn`.

### 5. Service

`assets/service.py`:

```python
"""Assets: the rules."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import audit, events
from app.core.errors import Conflict, NotFound
from app.core.time import utcnow
from app.modules.assets import access
from app.modules.assets.models import Asset
from app.modules.assets.schemas import AssetIn, AssetOut, LendIn
from app.modules.people.access import in_scope, scope_departments
from app.modules.people.models import Employee
from app.modules.platform.deps import Ctx


async def _asset(ctx: Ctx, asset_id: uuid.UUID, *, lock: bool = False) -> Asset:
    query = select(Asset).where(Asset.id == asset_id)
    if lock:
        query = query.with_for_update()
    asset = await ctx.db.scalar(query)
    # Missing, another workspace's (RLS hides it) or outside my departments: all 404.
    if asset is None or not await in_scope(ctx, asset.department_id):
        raise NotFound()
    return asset


async def list_assets(ctx: Ctx) -> list[AssetOut]:
    ctx.require(access.VIEW)
    query = select(Asset).order_by(Asset.tag)
    departments = await scope_departments(ctx)
    if departments is not None:
        query = query.where(Asset.department_id.in_(departments))
    return [AssetOut.model_validate(a) for a in await ctx.db.scalars(query)]


async def create(ctx: Ctx, body: AssetIn) -> AssetOut:
    ctx.require(access.MANAGE)
    if not await in_scope(ctx, body.department_id):
        raise NotFound()
    asset = Asset(tag=body.tag.upper(), name=body.name, department_id=body.department_id)
    ctx.db.add(asset)
    try:
        await ctx.db.flush()
    except IntegrityError:
        raise Conflict("Another asset already has this tag.", code="tag_taken") from None
    await audit.record(ctx.db, "asset.created", target_type="asset", target_id=asset.id,
                       data={"tag": asset.tag})
    await ctx.db.commit()
    return AssetOut.model_validate(asset)


async def lend(ctx: Ctx, asset_id: uuid.UUID, body: LendIn) -> AssetOut:
    ctx.require(access.MANAGE)
    asset = await _asset(ctx, asset_id, lock=True)
    if asset.status != "available":
        raise Conflict("This asset is already lent or retired.", code="asset_unavailable")
    if await ctx.db.get(Employee, body.employee_id) is None:
        raise NotFound()
    asset.status, asset.holder_id, asset.lent_at = "lent", body.employee_id, utcnow()
    await audit.record(ctx.db, "asset.lent", target_type="asset", target_id=asset.id,
                       data={"employee_id": body.employee_id})
    await events.emit(ctx.db, "asset.lent", subject_type="asset", subject_id=asset.id,
                      data={"employee_id": body.employee_id, "tag": asset.tag})
    await ctx.db.commit()
    return AssetOut.model_validate(asset)
```

(`get`, `return_asset` and `retire` follow the same shape.)

### 6. Routes

`assets/routes.py`:

```python
"""Assets API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.modules.assets import access, service
from app.modules.assets.schemas import AssetIn, AssetOut, LendIn
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/assets", tags=["assets"])
View = Depends(allow(access.VIEW, module="assets"))
Manage = Depends(allow(access.MANAGE, module="assets"))


@router.get("", response_model=list[AssetOut])
async def list_assets(ctx: Ctx = View) -> list[AssetOut]:
    return await service.list_assets(ctx)


@router.post("", response_model=AssetOut, status_code=201)
async def create(body: AssetIn, ctx: Ctx = Manage) -> AssetOut:
    return await service.create(ctx, body)


@router.post("/{asset_id}/lend", response_model=AssetOut)
async def lend(asset_id: uuid.UUID, body: LendIn, ctx: Ctx = Manage) -> AssetOut:
    return await service.lend(ctx, asset_id, body)
```

In `app/main.py`: import `router as assets_router` and add it to `ROUTERS`.

### 7. Module layers

In `api/pyproject.toml`, add `app.modules.assets` to the layer with `announcements`,
`attendance`, … (it uses `people` and `platform`, nothing else). `uv run lint-imports`.

### 8. Capability (so the assistant can answer "who has LAP-014?")

`assets/capabilities.py`:

```python
from pydantic import BaseModel
from app.modules.assets import access, service
from app.modules.assets.schemas import AssetOut
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx


class Nothing(BaseModel):
    pass


@capability("assets.list", "Company assets, their status and who holds them.",
            input=Nothing, output=list[AssetOut], permission=access.VIEW,
            module="assets", scoped=True, route="GET /v1/assets")
async def list_assets(ctx: Ctx, data: Nothing) -> list[AssetOut]:
    return await service.list_assets(ctx)
```

Import the file in `app/ai/tools.py` next to the others
(`from app.modules.assets import capabilities as _assets  # noqa: F401`), and add the capability to
the parity test's cases in `tests/test_capabilities.py`.

### 9. Notifications and webhooks (optional)

- Tell the borrower: in `notifications/subscribers.py`,
  `@events.on("asset.lent")` → create a notification for the employee's user.
  (Notifications sits *below* assets in the layers, so it can't import assets; it only
  reads the event's data, which is why events carry ids and short labels.)
- Tell customers' systems: add to `CATALOGUE` in `platform/webhooks.py`:
  `"asset.lent": Public("asset.lent", "An asset was lent to someone.", ("employee_id", "tag"))`.

### 10. Tests

`api/tests/test_assets.py`:

```python
import httpx
from tests.helpers import invite_and_join, signup


async def test_managers_lend_only_their_departments_assets(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "assets"]})
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    lead = await invite_and_join(owner, role="manager", scope_department_id=design["id"])

    laptop = (await owner.post("/v1/assets", json={"tag": "lap-1", "name": "Laptop",
                                                   "department_id": sales["id"]})).json()
    assert laptop["tag"] == "LAP-1"

    me = (await lead.get("/v1/people/me")).json()
    r = await lead.post(f"/v1/assets/{laptop['id']}/lend", json={"employee_id": me["id"]})
    assert r.status_code == 404                      # Sales isn't theirs

    r = await owner.post(f"/v1/assets/{laptop['id']}/lend", json={"employee_id": me["id"]})
    assert r.status_code == 200 and r.json()["status"] == "lent"
    r = await owner.post(f"/v1/assets/{laptop['id']}/lend", json={"employee_id": me["id"]})
    assert r.status_code == 409                      # already lent


async def test_assets_module_must_be_on(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    assert (await owner.get("/v1/assets")).status_code == 402
```

`uv run pytest -q tests/test_assets.py tests/test_isolation.py tests/test_platform.py --no-cov`
(the isolation sweep now covers `/v1/assets/{asset_id}/lend` automatically).

### 11. Web

1. `scripts/gen-api-types.sh`; in `web/src/api/types.ts`:
   `export type Asset = S["AssetOut"];`
2. `web/src/app/(product)/app/assets/page.tsx`:

```tsx
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Asset } from "@/api/types";
import { useSession } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { errorMessage } from "@/lib/errors";

export default function AssetsPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => api<Asset[]>("/v1/assets") });
  …
  return (
    <>
      <PageHeader title={t("assets.title")} actions={can("assets.manage") && <Button><Plus /> {t("assets.add")}</Button>} />
      {assets.data?.length === 0 && <EmptyState icon={<Laptop />} title={t("assets.empty")} />}
      …
    </>
  );
}
```

   Copy a dialog from a similar page (`expenses/page.tsx`) for "Add" and "Lend".
3. Nav: in `components/nav-items.ts`, add
   `{ href: "/app/assets", label: t("nav.assets"), short: t("nav.assets"), icon: Laptop, show: hasModule("assets") && can("assets.view") }`.
4. Texts: an `assets` block and `nav.assets` in **both** `en.ts` and `bn.ts`.
5. A browser journey (`e2e/assets.spec.ts`) if it matters: sign up, switch the module on,
   add, lend, see it in the list; `expectAccessible` and `watchCsp` on the page.

### 12. Finish

- Module card text on the public site only once it's built and tested (the site claims
  only what exists).
- Pricing: does it count towards `max_modules`? (It does, being a `Module`.)
- `docs/PROGRESS.md` line, help article in `components/help/articles.ts`.
- `E2E=1 scripts/check.sh` → `feat(assets): lend company equipment` → push → deploy.

## 12.4 Other common extensions, in brief

| I want to… | Where |
|---|---|
| A new email | `platform/emails.py` (both languages) + `emails.send(...)` in the service |
| A scheduled job | a function in the module, an `/internal/...` route with `internal_only`, a Cloud Scheduler job (chapter 10.3) |
| A new setting on the workspace | a column on `tenants` (global table) or a per-module settings table; `routes_workspace.py`; Settings page tab |
| A new AI feature | `app/ai/features.py` (the switch), a route in `app/ai/routes.py`, `workspace.require(ctx, "feature")` |
| A new AI provider | a class implementing `Model` in `app/ai/`, selected in `provider.py` |
| A new report figure | `reports/service.py` (and its schema), the Reports page |
| A new country preset | `leave/defaults.py`, `payroll/defaults.py` keyed by country; tax rates stay the workspace's own |
| A new language | a third file in `web/src/i18n`, email texts in `emails.py`, payslip fonts in `payroll/fonts` |
| Billing (M5) | `subscriptions.provider`/`provider_ref` already exist; add a Paddle webhook route (`public()`, signature-checked) that updates `plan_key`/`status`; `billing.manage` guards the UI |
