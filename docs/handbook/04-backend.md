# 4. The backend, file by file

## 4.1 FastAPI in ten minutes

FastAPI turns typed Python functions into HTTP endpoints:

```python
@router.get("/v1/announcements", response_model=list[AnnouncementOut])
async def feed(
    ctx: Ctx = Depends(allow("announcements.read", module="announcements")),
    limit: int = Query(default=30, ge=1, le=100),       # ?limit=…, validated
) -> list[AnnouncementOut]:
    return await service.feed(ctx, limit=limit)
```

- **Type hints drive validation and docs.** `limit: int = Query(ge=1, le=100)` means
  `?limit=500` gets a 422 before your code runs. `response_model` shapes the JSON and the
  OpenAPI document (from which the web types are generated).
- **Pydantic models** describe JSON bodies: `class AnnouncementIn(In): title: Name`.
- **`Depends(...)`** is dependency injection: FastAPI runs `allow(...)` first and passes
  its result (`Ctx`) in.
- **`async def`** lets one process serve many requests while waiting on the database.
  Never call blocking I/O (like `requests.get`) in an async function; use `httpx` or
  `asyncio.to_thread`.

Learn: [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) (first ten chapters),
[Pydantic models](https://docs.pydantic.dev/latest/concepts/models/),
[async in FastAPI](https://fastapi.tiangolo.com/async/).

## 4.2 The `api/` folder

```
api/
├── pyproject.toml          dependencies; ruff, mypy, pytest, coverage and import-linter settings
├── uv.lock                 exact versions (commit it; `uv sync` installs from it)
├── alembic.ini             migration settings
├── Dockerfile              the production image (built from the repo root)
├── migrations/
│   ├── env.py              runs migrations as MIGRATIONS_DATABASE_URL (cm_owner)
│   ├── rls.py              tenant_table / global_table / append_only helpers
│   └── versions/           20260930_0001_initial_schema.py … 20261005_0029_stock_revalue.py
├── app/
│   ├── main.py             builds the app: middleware, every router, /healthz, /readyz
│   ├── models_registry.py  imports every model so Alembic sees all tables
│   ├── core/               building blocks with no business knowledge (4.3)
│   ├── modules/            one folder per feature area (4.4, 4.5, chapter 5)
│   ├── ai/                 the assistant, actions, writing help, automation drafts (4.12)
│   └── jobs/maintenance.py the nightly job (purges, audit retention)
├── scripts/
│   ├── demo_seed.py        a tea house through the real API
│   ├── agency_week.py      a 30-person agency's week through the real API
│   └── api_contract.py     `check` / `accept` the public API snapshot (docs/api/openapi-v1.json)
└── tests/                  pytest, one file per area (chapter 9)
```

## 4.3 `app/core/`: the building blocks

| File | What it gives you |
|---|---|
| `config.py` | `get_settings()`: every setting from env vars / `.env`, validated. Refuses to start in staging/prod without keys or with a fake email/AI backend |
| `db.py` | the async engine; `get_db()` (a request's session); `open_session(tenant_id)` for jobs; `set_tenant()`; the `after_begin` hook that sets `app.tenant_id` on every transaction |
| `models.py` | `Base` with a naming convention; mixins `IdMixin` (UUIDv7 `id`), `TenantScoped` (`tenant_id`), `TimestampMixin`, `Versioned` (optimistic locking); stamps `tenant_id` on new rows |
| `ids.py` | `uuid7()`: time-ordered, unguessable ids |
| `schema.py` | `In` (rejects unknown fields, caps strings at 5,000 chars), `Out` (reads from ORM objects), `Page[T]`, and cleaned text types `Text`, `Name` (≤200), `ShortName` (≤120), `Note` (≤500): NFC-normalised, control characters removed, Bangla joiners kept |
| `errors.py` | `AppError` and `NotFound`, `Unauthorized`, `Forbidden`, `Conflict`, `PreconditionFailed`, `Invalid`, `PaymentRequired`, `TooManyRequests`, `Gone`, `Unavailable`; turns them (and validation errors) into RFC 9457 problem JSON |
| `http.py` | `etag()`, `set_etag()`, `check_if_match()`; opaque `encode_cursor()`/`decode_cursor()` for pagination; `read_body()` for streamed uploads with a limit; `deprecated()` for sunsetting endpoints |
| `middleware.py` | `RequestContextMiddleware` (request id, client IP, proxy-token check, size limits, security headers); `allow_upload(pattern, limit)` to give an upload route a bigger body |
| `idempotency.py` | `IdempotencyMiddleware`: `Idempotency-Key` replays for 24 h |
| `outbox.py` | `enqueue()`, `@handler(topic)`, `dispatch()`, `FlushMiddleware` (3.8) |
| `events.py` | `emit()`, `@on(name, later=False)`, the `domain_events` table (3.7) |
| `audit.py` | `record(db, action, target_type=…, target_id=…, data=…)`: appends to the hash-chained audit log; `verify_chain()`; sensitive keys redacted |
| `permissions.py` | `register(key, label, module=…, scoped=…, owner_only=…)`: the permission catalogue |
| `ratelimit.py` | fixed-window counters in Postgres; named `Rule`s; `enforce(rule, subject)` raises 429 with `Retry-After` |
| `email.py` | `Mail`; delivery by `console`, `memory` (tests) or `smtp`; always via the outbox (topic `email.send`) |
| `safehttp.py` | outbound HTTP to customer-chosen URLs: HTTPS only, public IPs only, connection pinned to the checked IP (webhooks, SSO discovery) |
| `ipnet.py` | CIDR allowlists, "is this a public address" |
| `captcha.py` | Cloudflare Turnstile verification |
| `context.py` | per-request info (request id, IP, user, tenant) readable anywhere, used by logs and the audit log |
| `logging.py` | JSON logs Cloud Logging understands |
| `time.py` | `utcnow()`, business-day helpers in a named time zone |
| `spreadsheet.py` | `safe_cell()`: stops CSV cells running as formulas in Excel |
| `security/passwords.py` | Argon2id hashing, breached-password check (100k list in `security/data/`), rules |
| `security/tokens.py` | EdDSA JWT access tokens; random opaque secrets stored as SHA-256 hashes; `same_secret()` (constant time) |
| `security/totp.py` | TOTP codes and recovery codes |
| `security/crypto.py` | AES-256-GCM field encryption with key ids (rotation) and the row id as associated data |

## 4.4 `app/modules/platform/`: accounts, workspaces, the developer platform

The lowest module; everything else builds on it.

| File | What's in it |
|---|---|
| `models.py` | `User`, `Tenant`, `Plan`, `Subscription`, `Membership`, `Role`, `Branch`, `AuthSession`, `RefreshToken`, `EmailToken`, `Invite`, `ApiKey`, `WebhookEndpoint`, `WebhookDelivery`, SSO settings and states… |
| `catalog.py` | platform permissions; `MODULES`; `BUSINESS_TYPES`; `BUILTIN_ROLES`; `resolve()` turns a role into a permission set |
| `deps.py` | `Ctx`, `Entitlements`, `allow()`, `signed_in()`, `public()`, `check_access()`, `member_ctx()` (a context for jobs acting as someone) |
| `workspaces.py` | creating a workspace (slug, trial, preset modules, roles, seed data hooks), module switching and plan limits |
| `tokens.py` | issuing sessions and refresh tokens, rotation and reuse detection, new-device alert emails |
| `routes_auth.py` | sign-up, email verification, sign-in (password, staff code + username), refresh, logout, two-step, step-up (`/reauth`), password reset/change, sessions, `/auth/me`, `/auth/switch`, `/plans`, `/modules` |
| `routes_workspace.py` | workspace settings, modules, members, staff accounts, invites, roles, branches, audit log and verification, delete/restore |
| `routes_join.py` | join links (with QR), `/v1/join`, the workspace's public card, its address |
| `routes_developers.py` | API keys, the network allowlist, audit export, sandbox workspaces |
| `routes_webhooks.py`, `webhooks.py` | endpoints, signing, the event catalogue, fan-out (queue only), `deliver_due()` with retries and auto-disable |
| `sso.py` | company sign-in with OpenID Connect (PKCE, nonce, provider keys); "require company sign-in" |
| `scim.py` | SCIM 2.0 users at `/v1/scim/v2` for Okta/Entra provisioning |
| `passkeys.py` | WebAuthn registration and sign-in |
| `support.py` | `POST /v1/support` ("Contact support") and anonymous usage counts |
| `internal.py` | `/internal/*` jobs: outbox, webhooks tick, daily clean-up |
| `emails.py` | every email text, English and Bangla, and `send()` |
| `hooks.py` | module seed hooks (what a module creates when switched on) |
| `capabilities.py` | the capability registry (3.10) |
| `ai_models.py` | AI settings and usage tables (owned here so modules never import `app.ai`) |

## 4.5 Anatomy of a module

Every feature folder has the same files. `announcements/` is the smallest complete one;
read it top to bottom once.

| File | Holds | Rule of thumb |
|---|---|---|
| `models.py` | SQLAlchemy tables | constraints in the database, not only in Python |
| `schemas.py` | Pydantic `…In` (requests), `…Patch`, `…Out` (responses) | every string has a length limit; `In` rejects unknown fields |
| `access.py` | `perms.register(...)` for the module's permissions | one place to see who may do what |
| `service.py` | the business logic, functions taking `ctx` first | **all rules live here**; commit here |
| `routes.py` | thin HTTP wrappers | parse, call the service, set ETag; nothing else |
| `capabilities.py` | the same reads/writes for the AI layer | mirrors a route; parity-tested |
| `defaults.py` (some) | starting data when the module is switched on | e.g. leave types, holidays, tax tables |
| `subscribers.py` (some) | `@events.on(...)` handlers | reactions to other modules' events |

### Models

```python
class Announcement(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "announcements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),                       # for composite FKs
        CheckConstraint("audience IN ('everyone', 'branches', 'departments')", name="audience"),
        Index("ix_announcements_feed", "tenant_id", "published_at"),
    )
    title: Mapped[str] = mapped_column(String(200))
    audience_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AnnouncementRead(TenantScoped, Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "announcement_id"],
                             ["announcements.tenant_id", "announcements.id"], ondelete="CASCADE"),
    )
```

### Permissions

```python
READ = perms.register("announcements.read", "Read announcements", module="announcements")
POST = perms.register("announcements.post", "Post announcements and see who has read them",
                      module="announcements", scoped=True)
```

`scoped=True` means: for a member with a scope department, this permission only reaches
inside that department's subtree. The service enforces what that means (here: a manager
can only address departments inside their scope).

### Service

```python
async def create(ctx: Ctx, body: AnnouncementIn) -> AnnouncementOut:
    ctx.require(access.POST)
    targets = await _check_audience(ctx, body.audience, body.audience_ids)   # scope rules
    post = Announcement(title=body.title, body=body.body, audience=body.audience,
                        audience_ids=targets, pinned=body.pinned,
                        published_at=utcnow(), author_id=ctx.user.id)
    ctx.db.add(post)
    await ctx.db.flush()                                   # get post.id without committing
    await audit.record(ctx.db, "announcement.published", target_type="announcement",
                       target_id=post.id, data={"title": post.title, "audience": post.audience})
    ctx.db.add(AnnouncementRead(announcement_id=post.id, user_id=ctx.user.id,
                                read_at=post.published_at))
    await _publish_event(ctx, post)                        # events.emit(...) → notifications
    await ctx.db.commit()
    return await get(ctx, post.id)
```

Habits worth copying:

- `ctx.require(...)` again in the service, even though the route checked: services have
  other callers.
- Look rows up through a helper (`_post(ctx, id, lock=True)`) that raises `NotFound` when
  the row is missing **or outside the caller's scope**.
- `flush()` when you need an id, `commit()` once at the end. The audit entry and the event
  commit with the change.
- Return an `…Out` model, never an ORM object.

### Routes

```python
router = APIRouter(prefix="/v1/announcements", tags=["announcements"])
Read = Depends(allow(access.READ, module="announcements"))

@router.patch("/{announcement_id}", response_model=AnnouncementOut)
async def update(announcement_id: uuid.UUID, body: AnnouncementPatch,
                 request: Request, response: Response, ctx: Ctx = Post) -> AnnouncementOut:
    check_if_match(request, (await service.get(ctx, announcement_id)).version)
    post = await service.update(ctx, announcement_id, body)
    set_etag(response, post.version)
    return post
```

Every route must declare its access with one of `public()`, `signed_in()`, `allow(...)` or
`internal_only`; `test_every_route_declares_who_may_call_it` in `tests/test_platform.py` fails if one doesn't, and `test_public_routes_are_the_expected_few` fails if you add a public route without listing it there. New routers
are added to `ROUTERS` in `app/main.py`.

## 4.6 Models and migrations

Write the model, then generate a migration and edit it:

```bash
cd api
uv run alembic revision --autogenerate -m "holiday notes"
```

Alembic writes `migrations/versions/<date>_<random>_holiday_notes.py`. Then:

1. Rename it like the others: `20261006_0030_holiday_notes.py`.
2. Set `revision = "0030"` and `down_revision = "0029"` inside.
3. For a **new tenant table**, add after `op.create_table(...)`:
   `rls.tenant_table("my_table")` (with `from migrations import rls`). Global table:
   `rls.global_table(...)`. Append-only: also `rls.append_only(...)`.
4. Read what autogenerate wrote. It misses: data changes, check-constraint changes
   (migration `0029` shows how to replace one: `op.drop_constraint(op.f("ck_…"))` then
   `op.create_check_constraint("kind", …)`; the naming convention adds the prefix),
   server defaults on existing rows, and anything RLS.
5. `uv run alembic upgrade head`, then `uv run alembic check` ("No new upgrade operations
   detected" means models and migrations agree; `check.sh` runs this).

Rules:

- **Never edit a migration that's already in production.** Write a new one.
- **Backward compatible:** the previous API revision must keep working on the new schema
  (Cloud Run rollbacks rely on it). Add columns as nullable or with a default; remove a
  column in a later release, after no code reads it.
- New model files must be imported in `app/models_registry.py`.

Learn: [SQLAlchemy 2 ORM quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html),
[asyncio extension](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html),
[Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

## 4.7 `Ctx`, permissions and scope

`Ctx` (in `platform/deps.py`) is everything a service needs to know about the caller:

| Field | Meaning |
|---|---|
| `db` | the request's `AsyncSession`, already bound to the workspace (RLS) |
| `user`, `session` | who, and how they signed in (`session.method`) |
| `tenant`, `membership`, `role` | which workspace, their membership and role |
| `permissions` | the resolved set (narrowed for API keys and till PINs) |
| `entitlements` | the plan, status, modules on, modules locked (over the limit), features |
| `api_key` | set when called with an API key |
| `cache` | per-request memo for expensive lookups |

Methods: `ctx.can("leave.approve")` → bool; `ctx.require(...)` raises 403;
`ctx.tenant_id`; `ctx.is_owner`; `ctx.scope_department_id`.

Scope helpers are in `people/access.py`: `scope_departments(ctx)` (the department ids the
caller covers, or `None` for everything) and `in_scope(ctx, department_id)`.

Route dependencies:

| Dependency | Who passes |
|---|---|
| `public()` | anyone (sign-up, the public workspace card, health checks) |
| `signed_in()` | any signed-in user, with or without a workspace (account settings) |
| `allow(permission, module=…)` | a member of the session's workspace with that permission (or `None`: any member) and the module on |
| `internal_only` | the scheduler, with `X-Internal-Token` |
| `owner_of_deleted_workspace()` | only for restoring a deleted workspace |

## 4.8 Conventions every endpoint follows

- **Errors**: raise `Invalid("…", errors=[{"field": "end", "message": "…"}])`,
  `NotFound()`, `Forbidden()`, `Conflict("…", code="…")`. Never return error dicts. The
  `code` is stable; the web app maps some to friendly text.
- **404, not 403**, for things outside the caller's scope, so nobody can probe what exists.
  403 is for "you can see it but may not do this".
- **402 `PaymentRequired`** for plan limits (`module_off`, `module_over_limit`,
  `workspace_read_only`, `api_not_in_plan`…).
- **Money**: integers in minor units. Quantities: `Decimal`. Never floats.
- **Time**: store instants as UTC `timestamptz`. A business date (which day a shift or a
  sale belongs to) is worked out in the branch's or workspace's time zone.
- **Lists**: return a plain list for small bounded sets; use `Page[T]` with
  `next_cursor` (opaque, from `encode_cursor`) for anything that grows.
- **Uploads**: the file is the raw request body (not multipart), with `allow_upload` for
  the route's size, `read_body()` to stream it with a limit, and the type checked by
  content (magic bytes), never by name. Downloads always come as attachments.
- **Concurrency**: versioned rows need `If-Match` on PATCH/PUT. Use
  `select(...).with_for_update()` when two requests could race on the same row (balances,
  drawer totals, stock).
- **Audit** anything that changes access, money, or someone's records.
- **Events** for anything another module or a customer's webhook might care about. Add a
  public one to the webhook catalogue in `webhooks.py` if customers should see it.

## 4.9 Emails

All email goes through the outbox, so it only leaves if the change commits:

```python
from app.modules.platform import emails
emails.send(ctx.db, "leave_approved", to=user.email, locale=user.locale,
            name=user.name, link=email.link("/app/leave"))
```

Texts live in `platform/emails.py` as `{kind: {"en": (subject, body), "bn": (…)}}` with
`{placeholders}`. Add both languages. Locally they're printed in the API terminal; tests
read them from the `memory` backend.

## 4.10 Rate limits

`core/ratelimit.py` keeps counters in a Postgres table (no Redis). Use a named rule:

```python
SUPPORT_RULE = ratelimit.Rule("support", 10, 3600)          # 10 per hour
await ratelimit.enforce(SUPPORT_RULE, str(ctx.user.id))      # 429 + Retry-After when over
```

Existing rules: sign-in per IP and per account, sign-up per IP, password reset, two-step
attempts, refresh, invites per workspace, writes per user (600/min), till unlocks, API key
creation, webhook test/resend, support messages, and each API key's own per-minute limit.

## 4.11 Domain events in code

```python
# emitting (in a service, before commit)
await events.emit(ctx.db, "expense.recorded", subject_type="expense", subject_id=row.id,
                  data={"amount": row.amount, "category_id": str(row.category_id)})

# reacting in the same transaction (a higher module)
@events.on("sale.completed")
async def _move_stock(db: AsyncSession, event: events.Event) -> None: ...

# reacting after commit, via the outbox, in its own transaction
@events.on("sale.completed", later=True)
async def _post_sale(db: AsyncSession, event: events.Event) -> None: ...
```

Subscribers register when their module is imported; `app/main.py` imports every router,
which imports every module. Keep event `data` small and JSON-friendly; subscribers
re-read anything they need.

## 4.12 The AI layer (`app/ai/`)

| File | What it does |
|---|---|
| `provider.py` | the port: `generate(system, turns, tools)`, `embed(texts)`; picks Gemini, the fake, or a workspace's own key (`with_key`) |
| `gemini.py` | Gemini over REST (`httpx`); tool names travel as `leave__balances`; schemas simplified for Gemini |
| `fake.py` | a scripted model for tests and demos (`AI_PROVIDER=fake`; refused in production) |
| `workspace.py` | is AI on here, which features, the plan's allowance and what's used; `require(ctx, feature)` |
| `features.py` | the list of AI features admins can tick |
| `tools.py` | turns the asker's capabilities into model tools and runs them as the asker |
| `assistant.py` | one question: up to six steps, numbered sources, saved conversation |
| `actions.py` | proposed writes: stored, shown, confirmed or cancelled by the asker within an hour |
| `writing.py` | draft, improve, shorten, translate |
| `brief.py` | the weekly brief from reports and pending approvals |
| `automations.py` | drafts an automation from plain words (for review in the editor) |
| `operator.py` | platform operators set allowances per plan; notifies workspaces |
| `context.py` | the context builder (who's asking, their workspace, today) |
| `routes.py` | `/v1/ai/*` and `/v1/operator/*` |

To add a provider: implement the `Model` protocol from `provider.py` in a new file and
select it there. Tests drive the assistant with
`provider.use_model(FakeModel(script=[Reply(...)]))`.

## 4.13 Async SQLAlchemy gotchas

- **`MissingGreenlet`** means something tried to load from the database lazily (a
  relationship, a `deferred` column, or an attribute expired by a commit or rollback).
  Select what you need in the query, or `await db.refresh(obj)` after a commit.
- `expire_on_commit=False` is set, so attributes survive `commit()`. A **rollback** still
  expires everything: capture values you need (ids, names) in local variables first.
- Raw SQL: `await db.execute(text("…"), {"x": 1})`. Never format values into SQL strings.
- One `AsyncSession` per request; never share it across concurrent tasks.

## 4.14 Daily commands

```bash
cd api
uv run pytest -q                          # all tests (about 10 minutes)
uv run pytest -q tests/test_leave.py      # one file
uv run pytest -q -k approve --no-cov      # by name, without the coverage gate
uv run pytest -q -x -s tests/test_x.py    # stop at the first failure, show prints
uv run ruff check . --fix && uv run ruff format .
uv run mypy app                           # strict type check
uv run lint-imports                       # module boundaries
uv run alembic upgrade head && uv run alembic check
uv run python -m scripts.api_contract check    # breaking changes to the public API?
uv run python -m scripts.api_contract accept   # after an intended, additive change
uv add <package>                          # add a dependency (updates uv.lock)
uv lock --upgrade-package <package>       # upgrade one
```

Learn: [uv](https://docs.astral.sh/uv/), [Ruff](https://docs.astral.sh/ruff/),
[mypy](https://mypy.readthedocs.io/en/stable/getting_started.html),
[pytest](https://docs.pytest.org/en/stable/getting-started.html).
