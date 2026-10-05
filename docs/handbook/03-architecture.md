# 3. Architecture

## 3.1 The shape of the system

```
                         ┌───────────────────────────── Cloudflare ─────────────────────────────┐
 Browser / phone ──TLS──▶│ DNS, TLS, WAF                                                         │
                         │ Pages: static files (site + app), per-page security headers (_headers)│
                         │ Pages Function web/functions/v1/[[path]].js: /v1/* ──┐                │
                         └──────────────────────────────────────────────────────│────────────────┘
                                                                                 │ + X-CM-Proxy-Token
                                                                                 │ + X-CM-Client-IP
                                                                                 ▼
                         ┌──────────── Google Cloud (asia-southeast1) ─────────────┐
 Cloud Scheduler ───────▶│ Cloud Run service companymgmt-api (FastAPI, 0→4 instances)│
  /internal/* + token    │ Cloud Run jobs: migrate, maintenance (nightly), backup    │
                         │ Secret Manager: keys, database URLs, tokens               │
                         └───────────────┬───────────────────────────────────────────┘
                                         │ SET LOCAL app.tenant_id per transaction
                                         ▼
                         Neon Postgres 16 (Singapore): forced row-level security
                         Resend (SMTP) for email · Gemini (optional) for AI · R2 for backups
```

It is a **modular monolith**: one API process, one database, the code split into modules
with enforced boundaries. There are no microservices, queues or caches to run. Everything
scales to zero when nobody uses it, which is what keeps the bill near zero (chapter 10).

| Layer | Technology | Where in the repo |
|---|---|---|
| Web (site + app) | Next.js 16 static export, React 19, TypeScript, Tailwind 4, Radix, TanStack Query, i18next | `web/` |
| Same-origin proxy | Cloudflare Pages Function | `web/functions/v1/[[path]].js` |
| API | Python 3.12, FastAPI, Pydantic 2 | `api/app/` |
| Data access | SQLAlchemy 2 (async) on psycopg 3 | `api/app/**/models.py` |
| Migrations | Alembic, numbered `0001…0029` | `api/migrations/` |
| Database | PostgreSQL 16 with forced RLS | Neon in production |
| PDFs | WeasyPrint with bundled Bangla fonts | `api/app/modules/payroll/pdf.py` |
| AI | Gemini over REST behind a provider port | `api/app/ai/` |
| Infrastructure | OpenTofu (Terraform) | `infra/gcp/` |
| Backups | `pg_dump` → `age` encryption → R2 | `infra/backup/` |

## 3.2 A request, end to end

Take "a manager approves a leave request":

```
1. Browser  POST /v1/leave/requests/{id}/approve   Authorization: Bearer <access JWT>
            (web/src/api/client.ts adds the token; refreshes once on 401)
2. Cloudflare Pages Function forwards to Cloud Run, adding X-CM-Proxy-Token and the
   client's real IP. (Locally: Next.js rewrite to :8000.)
3. FastAPI middleware, outermost first (api/app/main.py):
   a. RequestContextMiddleware   request id, client IP, proxy-token check, body size
                                 limits, security headers on the response
   b. CORSMiddleware             only the web origin (in production the browser never
                                 needs CORS: everything is same-origin)
   c. IdempotencyMiddleware      if Idempotency-Key is sent: replay the stored answer
   d. FlushMiddleware            collects the outbox events this request queues and
                                 delivers them just before the response starts
4. Route   api/app/modules/leave/routes.py
           ctx: Ctx = Depends(allow("leave.approve", module="leave"))
5. allow() api/app/modules/platform/deps.py
   - verifies the JWT, loads the session row (revoked? expired? user disabled?)
   - binds the DB session to the workspace: set_config('app.tenant_id', …)
   - loads membership + role, checks the IP allowlist and "company sign-in required"
   - resolves permissions; narrows them for API keys and till PIN sessions
   - check_access(): module on? over the plan's limit? workspace read-only? two-step
     required? permission held?
6. Service api/app/modules/leave/service.py  approve(ctx, request_id)
   - loads the request (RLS hides other workspaces; scope check hides other departments
     → 404, never 403)
   - business rules: not your own request, balance still enough, status is pending
   - changes the row, audit.record(…), events.emit(db, "leave.approved", …)
       → in-transaction subscribers run now (the bell notification for the requester)
       → "later" subscribers are queued in the outbox (webhooks, accounting…)
   - await ctx.db.commit()
7. FlushMiddleware delivers the queued outbox events (as their own transactions).
8. Response: JSON (Pydantic model), ETag for versioned rows, X-Request-Id.
```

Logic lives in **services**, never in routes, because services have three callers: REST
routes, AI **capabilities** (3.10) and scheduled jobs.

## 3.3 Modules and their boundaries

`api/app/modules/` holds one folder per feature area. `import-linter` (config at the
bottom of `api/pyproject.toml`, run by `uv run lint-imports`) enforces three contracts:

1. `app.core` never imports a module.
2. Modules never import `app.ai` (the AI layer sits on top of modules, not inside them).
3. Modules form layers; a module may only import modules **below** it.

The layers, top to bottom (exactly as in `pyproject.toml`; modules on one line are
independent of each other):

```
privacy
welcome
accounting
inventory · payroll
approvals · automations · imports · reports · sales
announcements · attendance · customers · documents · expenses · leave · notifications · tasks
people
platform
```

So `payroll` may use `people` and `attendance`, never the reverse. When a lower module
needs to cause something in a higher one (a sale must move stock and post to the books),
it **emits a domain event** and the higher module subscribes (3.7). That's how `sales`
knows nothing about `inventory` or `accounting`, yet a sale moves stock and posts itself.

## 3.4 Multi-tenancy: three layers of isolation

Every tenant table has a `tenant_id` column. Three independent layers keep workspaces apart;
any one of them failing alone leaks nothing.

**1. The application.** The workspace comes from the signed session (never from the URL
or the body). Membership, role and permissions are reloaded on every request, so removing
someone or changing their role takes effect on their very next call.

**2. The database (the important one).** Every tenant table has:

```sql
ALTER TABLE x ENABLE ROW LEVEL SECURITY;
ALTER TABLE x FORCE ROW LEVEL SECURITY;          -- applies to the table owner too
CREATE POLICY tenant_isolation ON x
  USING (tenant_id = app_current_tenant())
  WITH CHECK (tenant_id = app_current_tenant());
```

`app_current_tenant()` reads `current_setting('app.tenant_id')`. `core/db.py` sets it at the
start of **every transaction** (`after_begin` listener, `set_config(…, true)` =
transaction-local, safe behind Neon's PgBouncer pooler). A session with no tenant sees no
tenant rows at all. The API connects as `cm_app`, which owns no tables and has no
`BYPASSRLS`, so even a missing `WHERE tenant_id = …` in Python can't leak another
workspace's rows. New rows get their `tenant_id` stamped from the session
(`core/models.py`, `_stamp_tenant`), and a mismatched one raises.

Migrations call `rls.tenant_table("x")` (`api/migrations/rls.py`) for every new tenant
table. Global tables (users, tenants, plans, rate limits…) use `rls.global_table`.
Append-only tables (audit log, domain events) also get `rls.append_only`: the app role can
insert and read, never update or delete, and a trigger blocks changes even from the owner.

**3. References.** Tenant tables declare `UniqueConstraint("tenant_id", "id")` and point at
each other with **composite foreign keys** `(tenant_id, x_id)`, so a row can never reference
another workspace's row, even by a bug.

**Cross-workspace reads** (an operator's usage counts, "which workspaces does this user
belong to") go through `SECURITY DEFINER` SQL functions with a narrow, owner-only policy
(`app_user_workspaces`, `app_usage_counts`), never by turning RLS off.

**Proof:** `api/tests/test_isolation.py` checks every table has forced RLS, and calls
**every route that takes an id** (discovered automatically from the app) as workspace B
with workspace A's ids, expecting 404 or 422 and no change.

## 3.5 Identity: users, workspaces, sessions

- A **user** is a person (email, or username for staff without email) and can belong to
  several workspaces. A **membership** links a user to a workspace with a **role** and an
  optional **scope department**.
- Signing in creates an **auth session** (a row) tied to one workspace. The browser gets:
  - an **access token**: a 10-minute EdDSA JWT naming the session, kept only in memory;
  - a **refresh token**: random, in an `httpOnly; SameSite=Strict; Secure` cookie on the
    web origin, rotated on every use. Reusing an old one (outside a 10-second grace for
    two tabs) revokes the session: theft detection.
- `POST /v1/auth/switch` moves a session to another workspace the user belongs to.
- Session methods: `password`, `sso` (company sign-in), `passkey`, `pin` (a cashier on a
  registered till). A `pin` session only gets selling permissions (`PIN_PERMISSIONS`).
- **API keys** (`cmk_…`) authenticate as the member who made them, with at most the
  permissions chosen for the key and never owner-only ones; account routes refuse them.

Chapter 8 covers the security details.

## 3.6 Requests that must not happen twice

- **ETags / If-Match.** Versioned rows (`core/models.py`, `Versioned`) have a `version`.
  GET returns it as `ETag: W/"3"`; PATCH/PUT must send `If-Match`; if someone else saved
  first the API answers **412** and nothing is overwritten (`core/http.py`).
- **Idempotency keys.** Any write may carry `Idempotency-Key`. The first answer is stored
  for 24 hours per key or session; a retry gets the same answer with
  `Idempotent-Replayed: true`; the same key with a different body is refused
  (`core/idempotency.py`).
- **Client ids.** Offline till sales carry a `client_id`; the server keeps each sale once.

## 3.7 Domain events

`core/events.py`. When something important happens, a service calls:

```python
await events.emit(db, "leave.approved", subject_type="leave_request",
                  subject_id=row.id, data={"employee_id": …, "days": …})
```

This does three things, all inside the caller's transaction:

1. Writes a row to `domain_events` (append-only). The log and the data can never disagree,
   because they commit together or not at all.
2. Runs **in-transaction subscribers** (`@events.on("leave.approved")`): if one fails, the
   whole change fails. Used where the side effect must be atomic with the change:
   notifications, onboarding ticks, stock movements for a sale.
3. Queues one outbox row if any **later subscribers** exist
   (`@events.on("…", later=True)`): webhooks, accounting postings, automations.

Patterns: an exact name (`sale.completed`), a family (`leave.*`) or everything (`*`, used
by webhooks). Events caused by an automation carry `data["origin"]`, and automations ignore
those, so they can't trigger each other in loops.

Who listens to what is listed in chapter 13.5.

## 3.8 The outbox

`core/outbox.py`. Side effects that talk to the outside world (email, webhooks) or that
should run in their own transaction (accounting postings, automations) go through the
**transactional outbox**: a row in `outbox_events`, written in the same transaction as the
change. If the change rolls back, the side effect never happens; if it commits, the side
effect will happen at least once.

Delivery happens in two places:

1. **Right away, per request.** `FlushMiddleware` collects the ids queued during the
   request (a `ContextVar`) and, when the route has finished (and committed), delivers them
   just before the response starts. So the books show a sale the moment the till says
   "done", and a notification email leaves within the request.
2. **Retries, on a schedule.** `POST /internal/outbox/dispatch` (Cloud Scheduler) delivers
   anything still due, with exponential backoff (1, 2, 4, 8… minutes) for up to 8
   attempts. `SKIP LOCKED` lets several instances run it safely.

Handlers must be **idempotent** (safe to run twice), because "at least once" means a crash
between delivery and marking it delivered repeats it. Accounting postings, for example,
are keyed by their source so a second delivery changes nothing.

**Webhooks** are a special case: the `*` subscriber only **queues deliveries** in
`webhook_deliveries`; the per-minute `/internal/webhooks/tick` sends them, so a customer's
slow server never slows anyone's request.

## 3.9 Scheduled work

There's no background worker. Cloud Scheduler calls internal endpoints with the
`X-Internal-Token` header (a shared secret), and runs two Cloud Run jobs:

| What | How it's called | Suggested schedule | Does |
|---|---|---|---|
| Outbox retries | `POST /internal/outbox/dispatch` | every 10–30 min | delivers outbox events still due |
| Webhooks | `POST /internal/webhooks/tick` | every minute once customers use webhooks | sends due webhook deliveries, with retries |
| Automations | `POST /internal/automations/tick` | every 15 min | runs scheduled automations that are due, in each workspace's time zone |
| Daily clean-up | `POST /internal/maintenance/daily` | daily | deletes expired tokens, challenges, old outbox rows, rate-limit windows, idempotency keys, old webhook deliveries |
| Digest | `POST /internal/notifications/digest` | daily, morning | emails each person what they haven't read (once a day, their language) |
| Report emails | `POST /internal/reports/send` | daily | sends weekly/monthly reports on the first day of each workspace's week/month |
| Maintenance job | Cloud Run job `python -m app.jobs.maintenance` | nightly | purges workspaces deleted 30+ days ago (with a signed certificate), audit retention, old sign-in records |
| Backup job | Cloud Run job `infra/backup` | nightly | `pg_dump` → `age` → R2, keeps 30 days |

All of them are safe to run more than once. Chapter 10.6 gives the cheapest schedule.

## 3.10 Capabilities: one description, three callers

`api/app/modules/platform/capabilities.py` defines `@capability(...)`. Each module's
`capabilities.py` describes what it can do as typed functions:

```python
@capability("announcements.post", "Post an announcement to everyone, or to some branches…",
            input=AnnouncementIn, output=AnnouncementOut,
            permission=access.POST, module="announcements", kind="write",
            route="POST /v1/announcements")
async def post(ctx: Ctx, data: AnnouncementIn) -> AnnouncementOut:
    return await service.create(ctx, data)
```

The registry is what the AI layer sees. A capability runs through the same
`check_access()` as its REST route, as the person asking. A test
(`tests/test_capabilities.py`) proves every read capability returns **exactly** what its
route returns, and refuses exactly when the route refuses, for an owner, a scoped manager
and an employee.

## 3.11 The AI layer

`api/app/ai/` sits on top of every module and is the only place that talks to a model.

```
            question ──▶ assistant.py ──▶ provider.generate(system, turns, tools)
                              │                   │  (Gemini over REST, or FakeModel)
                              │◀── tool call ─────┘
                              ├─▶ tools.py: is it one of the asker's READ capabilities?
                              │      yes → run it as the asker (same checks as REST)
                              │      result goes back to the model as DATA, never instructions
                              └─▶ at most 6 steps → answer with numbered sources → saved
```

- **Off by default, everywhere.** No key on the server → every AI screen says so. With a
  key, each workspace's owner must accept the AI terms, and admins tick features
  (questions, documents, weekly brief, actions, writing help, automation drafts, signals).
- **Allowances** per plan per month (`workspace.py`), set by platform operators
  (`operator.py`).
- **Actions** (`actions.py`): the model may *propose* a write capability; nothing happens
  until the asker confirms it within an hour, and then it runs as them and is audited
  "via the assistant".
- **Own key:** a workspace may store its own Gemini key (encrypted) and use it instead.
- Threat model: `docs/security/ai.md`.

## 3.12 The web app

One Next.js project serves the public site and the product:

- `src/app/(site)/…` the public pages; `src/app/(product)/…` sign-in pages and `/app/…`.
- **Static export** (`output: "export"`): no Node server in production. Pages are HTML + JS
  that call `/v1` from the browser.
- After the build, `scripts/csp.mjs` writes `out/_headers`: a strict Content Security
  Policy **per page**, listing that page's own script hashes. No inline scripts anywhere.
- TypeScript types for every API call are **generated** from the API's OpenAPI document
  (`scripts/gen-api-types.sh` → `web/src/api/schema.d.ts`), and `check.sh` fails if
  they're stale, so the two sides can't drift apart.

Chapter 6 walks through it.

## 3.13 Why these choices

| Choice | Instead of | Because |
|---|---|---|
| Modular monolith | microservices | one person can run it; boundaries are still enforced by import-linter |
| Postgres RLS | only `WHERE tenant_id` in code | a forgotten filter can't leak data |
| Static export + Pages | a Node server | free hosting, no server to patch, strict CSP per page |
| Same-origin `/v1` proxy | API on its own domain | first-party cookie (works on `*.pages.dev` too), no CORS, the API can't be called around the proxy |
| Cloud Run, scale to zero | a VM | costs nothing when idle, no OS to maintain |
| Neon | Cloud SQL | free tier, scale to zero, point-in-time restore, branching for drills |
| Outbox + scheduler | a queue (Pub/Sub, Redis) | nothing else to run or pay for; atomic with the data |
| Events between modules | modules calling each other | lower modules stay unaware of higher ones; new features subscribe without touching old code |
| Integers for money | floats | no rounding drift |
| UUIDv7 ids | serial ints | sortable by time, not guessable, safe to generate anywhere |
