# The CompanyMgmt developer guide

This guide is for you, the owner, picking up the code yourself. It assumes you can use a
terminal and have written a little code before, but not that you know any of the tools used
here. It goes from "run it on my laptop" to "add a feature the way the rest of the code does
it", and links to a good tutorial whenever a new idea comes up.

Read it in order the first time. After that, use the table of contents as a reference.

1. [Run it on your computer](#1-run-it-on-your-computer)
2. [The big picture](#2-the-big-picture)
3. [A tour of the repository](#3-a-tour-of-the-repository)
4. [The backend (api/)](#4-the-backend-api)
5. [The frontend (web/)](#5-the-frontend-web)
6. [Tests and the checks before every push](#6-tests-and-the-checks-before-every-push)
7. [Walkthrough: adding a feature end to end](#7-walkthrough-adding-a-feature-end-to-end)
8. [Deploying](#8-deploying)
9. [Cookbook: everyday tasks](#9-cookbook-everyday-tasks)
10. [Troubleshooting](#10-troubleshooting)
11. [Glossary and learning links](#11-glossary-and-learning-links)
12. [A study plan](#12-a-study-plan)

---

## 1. Run it on your computer

### 1.1 What you need to install

| Tool | Why | Get it |
|---|---|---|
| **Git** | Downloads the code and tracks changes | <https://git-scm.com/downloads> |
| **Python 3.12** | The API is written in Python | <https://www.python.org/downloads/> (3.12 or 3.13) |
| **uv** | Installs Python packages and runs Python tools (a faster `pip` + `venv`) | <https://docs.astral.sh/uv/getting-started/installation/> |
| **Node.js 22** | Builds and runs the web app | <https://nodejs.org/> (the "LTS" 22.x) |
| **PostgreSQL 16** | The database | <https://www.postgresql.org/download/> |
| **Pango** (system library) | WeasyPrint needs it to draw payslip PDFs | Linux: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`; Mac: `brew install pango`; Windows: see the [WeasyPrint install notes](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) |

**On Windows**, the easiest path is [WSL 2](https://learn.microsoft.com/windows/wsl/install)
(Ubuntu inside Windows). Install everything above inside Ubuntu and follow the Linux
commands. The scripts in `scripts/` are bash scripts and expect Linux or a Mac.

Check that it all works:

```bash
git --version        # any recent version
python3 --version    # 3.12.x or 3.13.x
uv --version         # 0.8 or later
node --version       # v22.x
psql --version       # 16.x
```

### 1.2 Get the code

```bash
git clone https://github.com/omikhan4901/companymgmt.git
cd companymgmt
```

### 1.3 Create the database

The API uses three Postgres **roles** (database users), on purpose. Section 4.4 explains why.
One script creates them, plus two databases: `companymgmt` for the app and
`companymgmt_test` for the tests.

```bash
# Linux: Postgres must be running first
sudo service postgresql start          # or: sudo systemctl start postgresql
scripts/dev-db.sh                      # safe to run again; it only creates what's missing
```

On a Mac with Homebrew Postgres there's no `postgres` system user. Give the script a
superuser connection instead:

```bash
ADMIN_DATABASE_URL=postgresql://$(whoami)@localhost:5432/postgres scripts/dev-db.sh
```

### 1.4 Settings (.env)

```bash
cp .env.example .env
```

The defaults in `.env.example` work locally as they are. Every variable is explained in that
file. Never commit `.env`; it's in `.gitignore`.

### 1.5 Start the API (terminal 1)

```bash
cd api
uv sync                        # installs Python packages into api/.venv (first time: a minute)
uv run alembic upgrade head    # creates the tables (run again whenever you pull new code)
uv run uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000/docs>: that's the **interactive API documentation** (Swagger UI),
generated from the code. Every endpoint is listed there, and you can try them in the browser.

`--reload` restarts the server whenever you save a Python file.

### 1.6 Start the web app (terminal 2)

```bash
cd web
npm install                    # first time only (or when package.json changes)
npm run dev                    # http://localhost:3000
```

In development, Next.js forwards every request for `/v1/...` to the API on port 8000 (see
`web/next.config.ts`), so the browser only ever talks to `localhost:3000`.

Open <http://localhost:3000>. You'll see the marketing site. Click **Get started** to create
a workspace (emails are printed in terminal 1 instead of being sent, because
`EMAIL_BACKEND=console`).

### 1.7 Demo data (optional, terminal 3)

Two scripts fill a workspace through the real API, as a user would:

```bash
cd api
uv run python -m scripts.demo_seed      # a small tea house: attendance, leave, payroll
uv run python -m scripts.agency_week    # a 30-person agency's week: tasks, news, policies…
```

Each prints the email and password to sign in with. `agency_week` signs thirty people in
from your computer. The sign-in limit is 30 per 5 minutes per address, so run it at most
once every five minutes, or add `LOGIN_LIMIT_PER_IP=1000` to your `.env` while developing.

### 1.8 Stopping and starting again

Press `Ctrl+C` in each terminal to stop. Next time you only need:

```bash
sudo service postgresql start                                # if it isn't running
cd api && uv run uvicorn app.main:app --reload --port 8000   # terminal 1
cd web && npm run dev                                        # terminal 2
```

After `git pull`, also run `uv sync`, `uv run alembic upgrade head` (in `api/`) and
`npm install` (in `web/`), in case something changed.

---

## 2. The big picture

### 2.1 What the product is

A multi-tenant SaaS: many companies ("workspaces", also called "tenants") share one
deployment, and each company only ever sees its own data. Inside a workspace, people have
**roles** (owner, admin, manager, employee…). A role is a list of **permissions**, and a
manager's permissions can be **scoped** to one department and everything under it.

Features are grouped in **modules** (attendance, leave, payroll, tasks…). A workspace
switches modules on or off, and the **plan** it pays for limits how many people and modules
it can have.

### 2.2 How a request travels

```
 Browser (React app, static files)
   │  fetch("/v1/leave/requests")  + Authorization: Bearer <access token>
   ▼
 Same-origin /v1 proxy
   dev:  Next.js rewrite (web/next.config.ts)
   prod: Cloudflare Pages Function (web/functions/v1/[[path]].js)
   ▼
 FastAPI app (api/app/main.py)
   ├─ middleware (api/app/core/middleware.py): request id, size limits, security headers
   ├─ route function (api/app/modules/<module>/routes.py)
   │     Depends(allow("leave.view", module="leave"))
   │       → checks the token, loads user + workspace + role
   │       → binds the DB session to the tenant (RLS)
   │       → checks the permission and that the module is on
   │       → returns a Ctx (the request "context")
   ├─ service function (api/app/modules/<module>/service.py): the business logic
   ▼
 PostgreSQL: every query is filtered to the current tenant by row-level security
```

The same service functions are also called by **capabilities** (section 4.10), the layer
the AI assistant will use in a later milestone. That's why logic lives in services, not routes.

### 2.3 The stack, in one table

| Layer | Technology | Where |
|---|---|---|
| Web UI | Next.js 16 (React 19, TypeScript), exported as static files | `web/` |
| Styling | Tailwind CSS 4 + Radix UI primitives, "Atlas" design tokens | `web/src/app/globals.css`, `web/src/components/ui` |
| Data fetching | TanStack Query + a small `api()` client | `web/src/api` |
| Forms | react-hook-form | in each page/component |
| Languages | i18next, English and Bangla | `web/src/i18n/en.ts`, `bn.ts` |
| API | FastAPI (Python 3.12), Pydantic v2 | `api/app` |
| Database access | SQLAlchemy 2 (async) + psycopg 3 | `api/app/**/models.py` |
| Migrations | Alembic | `api/migrations` |
| Database | PostgreSQL 16 with row-level security | |
| PDFs | WeasyPrint (HTML → PDF) | `api/app/modules/payroll` |
| Tests | pytest (API), Vitest (web units), Playwright + axe (browser) | `api/tests`, `web/src/**/*.test.ts`, `web/e2e` |
| Hosting (planned) | Google Cloud Run (API), Neon (Postgres), Cloudflare Pages (web) | `infra/`, `docs/runbooks/deploy.md` |

---

## 3. A tour of the repository

```
companymgmt/
├── README.md                 what the product does, status, future work
├── CLAUDE.md                 rules for AI assistants working on the repo (useful for you too)
├── .env.example              every setting, documented, with no secret values
├── scripts/
│   ├── check.sh              runs every check CI runs. Run before every push
│   ├── dev-db.sh             creates local roles and databases
│   ├── gen-api-types.sh      regenerates the web app's TypeScript types from the API
│   └── gen-keys.sh           makes signing keys for staging/production
├── api/                      the backend
│   ├── pyproject.toml        Python dependencies + tool settings (ruff, mypy, pytest, import rules)
│   ├── alembic.ini           migration tool settings
│   ├── migrations/           one file per database change, in order (0001 … 0014)
│   │   └── rls.py            helpers that switch on row-level security for a table
│   ├── app/
│   │   ├── main.py           creates the FastAPI app and includes every router
│   │   ├── models_registry.py imports every model so Alembic sees all tables
│   │   ├── core/             shared building blocks (no business features)
│   │   ├── modules/          one folder per feature area (see 4.2)
│   │   ├── ai/               the capability/tool layer for the future assistant
│   │   └── jobs/             nightly maintenance
│   ├── scripts/              demo_seed.py, agency_week.py
│   └── tests/                pytest tests, one file per area
├── web/                      the frontend (marketing site + product)
│   ├── src/app/(site)/       marketing pages: /, /pricing, /legal/…
│   ├── src/app/(product)/    sign-in pages and the app under /app/…
│   ├── src/components/       React components; ui/ holds the design-system pieces
│   ├── src/api/              api() client, generated types, shared query hooks
│   ├── src/auth/             session state (who is signed in, which workspace)
│   ├── src/i18n/             all English and Bangla text
│   ├── src/lib/              small helpers (dates, money, formatting) with unit tests
│   ├── e2e/                  Playwright browser tests
│   ├── scripts/csp.mjs       writes per-page security headers after the build
│   ├── scripts/serve.mjs     serves the built site locally like Cloudflare does
│   └── functions/v1/         the Cloudflare function that proxies /v1 to the API
├── infra/                    OpenTofu (Terraform) for Google Cloud, backup scripts
└── docs/
    ├── IMPLEMENTATION_PLAN.md the roadmap: every milestone and why
    ├── PROGRESS.md           what's done, decisions made, a dated log
    ├── GUIDE.md              this file
    ├── runbooks/             deploy.md, restore.md: step-by-step operations
    ├── security/asvs-l2.md   the security checklist (OWASP ASVS level 2) and evidence
    ├── design/               the Atlas design direction
    └── marketing/            copy, case study, demo script
```

---

## 4. The backend (api/)

### 4.1 FastAPI in five minutes

FastAPI turns Python functions into HTTP endpoints. A route looks like this:

```python
@router.get("/v1/leave/requests", response_model=list[RequestOut])
async def list_requests(
    status: Literal["pending", "approved", "all"] = "all",   # a ?status= query parameter
    ctx: Ctx = Depends(allow(access.SELF, module="leave")),  # who is calling, and may they?
) -> list[RequestOut]:
    return await service.list_requests(ctx, status=status)
```

- **Type hints drive everything.** `status: Literal[...]` means FastAPI validates the query
  parameter and returns a 422 error for anything else. `response_model` shapes and
  documents the output.
- **Pydantic models** (`class RequestOut(BaseModel)`) describe JSON bodies. FastAPI checks
  incoming JSON against them before your code runs.
- **`Depends(...)`** is dependency injection: FastAPI calls `allow(...)` first and passes
  its result in as `ctx`.
- **`async def`** lets one server process handle many requests while waiting on the database.

Learn: the official [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) (do the
first ~10 chapters), [Pydantic v2 concepts](https://docs.pydantic.dev/latest/concepts/models/),
and [async/await in Python](https://fastapi.tiangolo.com/async/).

### 4.2 Anatomy of a module

Every folder in `api/app/modules/` follows the same shape. Take `leave/`:

| File | What goes in it |
|---|---|
| `models.py` | Database tables, as SQLAlchemy classes (`class LeaveRequest(...)`). |
| `schemas.py` | Pydantic shapes for the API: `...In` (what clients send) and `...Out` (what they get). |
| `access.py` | The module's permissions, e.g. `APPROVE = perms.register("leave.approve", ...)`. |
| `service.py` | The business logic. Functions take `ctx` first. **All the rules live here.** |
| `routes.py` | Thin HTTP wrappers: parse the request, call the service, return the result. |
| `capabilities.py` | The same reads/writes described for the AI layer (4.10). |
| `defaults.py` | Starting data when a workspace switches the module on (leave types, holidays…). |

The modules, roughly from the bottom of the stack to the top:

- `platform`: accounts, sign-in, workspaces, members, roles, plans, branches, audit log
- `people`: employee profiles and the department tree
- `attendance`: clock in/out (with location checks), records, time fixes, timesheets
- `leave`: leave types, balances, requests, holidays, the team calendar
- `tasks`: projects, tasks, checklists, comments, onboarding checklists
- `announcements`, `documents`, `notifications`
- `approvals`: one inbox over leave and time-fix requests
- `payroll`: salaries, pay runs, payslips (PDF), advances; Bangladesh tax and rules
- `imports`: the spreadsheet import; `reports`: the overview report and report emails
- `privacy`: workspace export/import, deletion

**Who may import whom** is enforced by `import-linter` (config at the bottom of
`api/pyproject.toml`). `core` never imports a module. A module only imports modules
*below* it (e.g. `payroll` may use `people`, never the reverse). `uv run lint-imports`
fails if someone breaks this. Modules talk "upwards" through **events** instead (4.8).

### 4.3 The request context (`Ctx`) and permissions

`api/app/modules/platform/deps.py` defines `Ctx`: the signed-in `user`, their
`membership`, `role`, the `tenant`, the resolved `permissions`, the plan's `entitlements`,
and `db` (the database session for this request).

- `allow("leave.approve", module="leave")` on a route: must be signed in, a member of the
  workspace, have the permission, and have the module switched on.
- In services: `ctx.require(access.APPROVE)` raises 403 if missing; `ctx.can(...)` returns
  a bool.
- **Scope:** `ctx.scope_department_id` is set for scoped members (e.g. a manager of
  "Design"). Helpers in `people/access.py` turn it into the list of departments they cover:
  `scope_departments(ctx)`, `in_scope(ctx, department_id)`.
- Built-in roles and their permissions are in `platform/catalog.py` (`BUILTIN_ROLES`).
  Owners have `*` (everything).
- `member_ctx(db, tenant, membership)` builds the same context outside a request, for
  scheduled jobs that act on someone's behalf (used by the report emails).

### 4.4 Multi-tenancy and row-level security (the most important idea)

Every company's rows live in the same tables, each with a `tenant_id` column. Two layers
keep companies apart:

1. **Postgres row-level security (RLS).** Each tenant table has a policy:
   `tenant_id = app_current_tenant()`. At the start of each request the API runs
   `set_config('app.tenant_id', <id>, true)` (see `core/db.py`), and Postgres itself
   hides every other tenant's rows, even if the Python code forgets a `WHERE`.
2. **The API connects as `cm_app`**, a role that doesn't own the tables and can't bypass RLS.
   Migrations run as `cm_owner`. That's why there are two database URLs in `.env`.

When you add a table, your migration must call `rls.tenant_table("my_table")`.
`tests/test_isolation.py` checks every table and fails if one is unprotected. It also calls
every API route with another workspace's ids and expects 404.

Learn: [PostgreSQL row security policies](https://www.postgresql.org/docs/16/ddl-rowsecurity.html),
and the idea of [multi-tenant SaaS data isolation](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/).

### 4.5 Database models and migrations

Models use SQLAlchemy 2's typed style:

```python
class Holiday(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "holidays"
    day: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(120))
```

The mixins in `core/models.py` add `id` (UUIDv7: sortable by time), `tenant_id`,
`created_at`/`updated_at`, and `version` (`Versioned`, for safe concurrent edits, 4.7).

To change the database:

```bash
cd api
# 1. edit models.py
uv run alembic revision --autogenerate -m "what changed"   # writes migrations/versions/<date>_<id>_….py
# 2. open the new file: rename it like the others (…_0015_short_name.py), set
#    revision = "0015" and down_revision = "0014", and add rls.tenant_table(...) for new tables
uv run alembic upgrade head
uv run alembic check        # "No new upgrade operations detected" = models and DB agree
```

If a model isn't imported in `app/models_registry.py`, Alembic won't see it.

Learn: [SQLAlchemy 2.0 ORM quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html),
[SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html),
[Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

A gotcha you'll hit: with async SQLAlchemy you can't lazily load a relationship or a
`deferred` column after the fact (you get `MissingGreenlet`). Select what you need in the
query itself.

### 4.6 Sign-in, tokens and security

- **Passwords** are hashed with Argon2id and checked against a list of 100,000 breached
  passwords (`core/security/passwords.py`).
- **Access token:** a short-lived (10 min) signed JWT (EdDSA), kept only in the browser's
  memory, sent as `Authorization: Bearer …`.
- **Refresh token:** a long random value in an `httpOnly`, `SameSite=Strict` cookie. The web
  client calls `/v1/auth/refresh` to get a new access token. Each refresh replaces the token;
  reusing an old one ends the session (theft detection).
- **MFA:** TOTP codes (Google Authenticator etc.) plus recovery codes; owners can require it.
- **Step-up:** sensitive actions ask for the password again within 5 minutes.
- **Rate limits** (`core/ratelimit.py`) on sign-in, sign-up, password reset; a CAPTCHA
  (Cloudflare Turnstile) after repeated failures.
- **Staff accounts** without email sign in with a workspace code + username.
- **Field encryption:** national IDs and bank accounts are encrypted in the database
  (AES-256-GCM, `core/security/crypto.py`).
- **Audit log:** `audit.record(db, "leave.approved", …)` appends to a hash-chained log that
  the app can't edit or delete.

The full checklist with evidence: `docs/security/asvs-l2.md`.

Learn: [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/),
[JWT introduction](https://jwt.io/introduction), [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[TOTP explained](https://en.wikipedia.org/wiki/Time-based_one-time_password).

### 4.7 Conventions every endpoint follows

- **Errors** are [RFC 9457 problem details](https://www.rfc-editor.org/rfc/rfc9457):
  `{"title", "detail", "code", "errors": [{"field", "message"}]}`. Raise `Invalid`,
  `NotFound`, `Forbidden`, `Conflict` from `core/errors.py`; never return error dicts by hand.
  The `code` is stable; the web app translates some codes into friendly text.
- **Concurrent edits:** editable things have a `version`. `GET` returns it as an `ETag`;
  `PATCH` must send `If-Match: W/"<version>"`. If someone else changed it first, the API
  answers 412 and nothing is overwritten (`core/http.py`: `check_if_match`, `set_etag`).
- **Not found vs forbidden:** asking for something outside your scope returns 404, not 403,
  so people can't probe for what exists.
- **Money** is integer minor units (paisa): `150000` means ৳1,500.00. Never floats.
- **Time:** instants are stored as UTC (`timestamptz`); a "business date" (which day a shift
  belongs to) is worked out in the branch's time zone (`core/time.py`).
- **Uploads** take the file as the raw request body, with a per-route size limit
  (`allow_upload` in `core/middleware.py`) and content checked by magic bytes, not by name.
- **Audit:** any change that matters calls `audit.record(...)`.

### 4.8 Events, notifications and the outbox

When something happens, a service emits a **domain event**:

```python
await events.emit(db, "leave.approved", subject_type="leave_request", subject_id=row.id,
                  actor_user_id=ctx.user.id, data={...})
```

Other modules subscribe without the emitter knowing about them:

```python
@events.on("leave.approved")
async def tell_the_person(db, event): ...
```

That's how notifications work (`notifications/subscribers.py`) and how onboarding items tick
themselves off when a document is acknowledged. Events are stored, so a future automation
engine can read them.

The **outbox** (`core/outbox.py`) makes side effects like email reliable: the email is saved
in the same database transaction as the change, then sent after commit (and retried every
10 minutes if sending failed). If the transaction rolls back, no email goes out.

Learn: [the transactional outbox pattern](https://microservices.io/patterns/data/transactional-outbox.html).

### 4.9 Scheduled jobs

Cloud Scheduler calls `/internal/*` endpoints with a shared secret header
(`X-Internal-Token`): the outbox dispatcher, nightly maintenance, the daily notification
digest and the report emails. Locally you can call them yourself, e.g. in a Python shell:
`await send_reports()` from `app.modules.reports.subscriptions`. The schedule is in
`docs/runbooks/deploy.md`.

### 4.10 Capabilities: the layer the AI will use

`@capability(...)` in each module's `capabilities.py` describes one read or write: its
input and output schema, the permission it needs and the REST route it mirrors. The AI
assistant (milestone M6) will only ever reach data through these. Never through the database
directly. `tests/test_capabilities.py` proves that every read capability answers, and refuses,
exactly like its REST route, for an owner, a manager and a staff member.

### 4.11 Python tooling you'll use daily

```bash
cd api
uv run pytest -q                       # all tests (~4–5 minutes)
uv run pytest -q tests/test_leave.py   # one file
uv run pytest -q -k approve            # tests whose name contains "approve"
uv run ruff check . --fix              # lint (and fix what it can)
uv run ruff format .                   # format
uv run mypy app                        # type check (strict)
uv run lint-imports                    # module boundaries
```

Learn: [uv](https://docs.astral.sh/uv/), [Ruff](https://docs.astral.sh/ruff/),
[mypy for beginners](https://mypy.readthedocs.io/en/stable/getting_started.html),
[pytest](https://docs.pytest.org/en/stable/getting-started.html).

---

## 5. The frontend (web/)

### 5.1 Next.js, used as a static site

The web app is built with [Next.js](https://nextjs.org/docs/app) (App Router) but **exported
as plain static files** (`output: "export"` in `next.config.ts`). There's no Node server in
production: Cloudflare serves the HTML/JS, and the pages fetch data from the API in the
browser. Every page under `src/app/(product)` starts with `"use client"`.

- **Routing is folders:** `src/app/(product)/app/leave/page.tsx` is the page at `/app/leave`.
  Folders in parentheses, `(site)` and `(product)`, are **route groups**: they organise code
  and share a `layout.tsx`, but don't appear in the URL.
- `src/app/(product)/app/layout.tsx` wraps every app page in the **app shell**
  (`components/app-shell.tsx`): the side rail on desktop, the bottom bar on phones, the
  header with search, notifications and language.
- State that should survive a reload lives in the URL (`?tab=…`, `?task=…`): see
  `lib/use-tab.ts`.

Learn: [React: Thinking in React](https://react.dev/learn/thinking-in-react) and the
[React "Learn" section](https://react.dev/learn), the
[Next.js App Router docs](https://nextjs.org/docs/app) and
[static exports](https://nextjs.org/docs/app/guides/static-exports), and
[TypeScript for JS programmers](https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes.html).

### 5.2 Talking to the API

- `src/api/client.ts`: `api<T>(path, options)` adds the access token, refreshes it once on
  a 401, sends `If-Match` when you pass `version`, and throws `ApiError` with the problem
  details. `download()` saves files.
- `src/api/schema.d.ts`: **generated** TypeScript types for every API request and response.
  Never edit it by hand: run `scripts/gen-api-types.sh` after changing the API. `check.sh`
  fails if it's out of date. `src/api/types.ts` gives the generated types friendly names
  (`export type Task = S["TaskOut"]`).
- **TanStack Query** caches server data. A read is `useQuery({ queryKey, queryFn })`; a
  change is `useMutation({ mutationFn, onSuccess })`. After a change, *invalidate* the
  affected keys so lists refetch:
  `queryClient.invalidateQueries({ queryKey: ["tasks"] })`. Query keys are arrays; anything
  starting with `["tasks"]` is invalidated by that call. Each feature keeps its keys and
  hooks in a `data.ts` file (e.g. `components/tasks/data.ts`).

Learn: [TanStack Query overview](https://tanstack.com/query/latest/docs/framework/react/overview)
and [invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation).

### 5.3 Forms

Forms use [react-hook-form](https://react-hook-form.com/get-started): `useForm` with
`defaultValues`, `register("field")` on inputs, `handleSubmit`. Server-side field errors are
put next to their fields with `applyFieldErrors` (`lib/errors.ts`). Two habits:

- When a form's data loads late, reset with `resetOptions: { keepDirtyValues: true }` so
  what the person already typed isn't wiped (there's a browser test for this).
- Watch a value with `useWatch({ control, name })`, not `watch()`. The linter enforces it.

### 5.4 Design system and styling

- **Tailwind CSS** classes for styling (`className="flex gap-3 rounded-xl p-4"`). Learn:
  [Tailwind core concepts](https://tailwindcss.com/docs/styling-with-utility-classes).
- **Atlas tokens:** colours like `bg-surface`, `text-muted`, `bg-accent-soft`,
  `text-danger-text` are defined once in `src/app/globals.css` and switch automatically for
  dark mode and the four accent colours (`lib/theme.tsx`). Use tokens, never raw colours.
- **Components in `src/components/ui`**: `Button`, `Input`, `Select`, `Field` (label + help
  + error, wired for screen readers), `Dialog`/`SheetContent`, `Tabs`, `Badge`, `Card`,
  `Table`, `ConfirmDialog`… Most wrap [Radix UI](https://www.radix-ui.com/primitives/docs/overview/introduction)
  primitives, which handle keyboard and screen-reader behaviour.
- Icons come from [lucide-react](https://lucide.dev/icons/).
- Design rules (calm, little text, one clear next action, dialogs never full-screen on
  desktop, sheets on phones) are in `CLAUDE.md` and `docs/design/atlas`.

### 5.5 Languages

Every visible string is a key: `t("leave.approve")`. The texts are in `src/i18n/en.ts` and
`src/i18n/bn.ts`; TypeScript fails if a key exists in one and not the other. Plurals use
`_one`/`_other` keys and a `count`; numbers are formatted with `formatNumber` (Bangla
digits in Bangla). Dates use `formatDay`. Learn: [react-i18next](https://react.i18next.com/)
and [i18next plurals](https://www.i18next.com/translation-function/plurals).

### 5.6 Security in the browser

The build writes `out/_headers` (`scripts/csp.mjs`) with a strict
[Content Security Policy](https://developer.mozilla.org/docs/Web/HTTP/Guides/CSP) per page:
only that page's own scripts, by hash. So: **no inline scripts and no
`dangerouslySetInnerHTML`**. Anything that must run before the page paints goes in
`public/*.js`. The browser tests fail on any CSP violation.

### 5.7 Web commands

```bash
cd web
npm run dev          # development server with hot reload
npm run lint         # ESLint
npm run typecheck    # TypeScript
npm test             # Vitest unit tests (src/lib/*.test.ts)
npm run build        # production build into out/ (+ security headers)
npm run serve        # serve out/ like Cloudflare, proxying /v1 to the API
```

---

## 6. Tests and the checks before every push

### 6.1 API tests (pytest)

- They run against a **real Postgres** (`companymgmt_test`), because RLS can't be faked.
  The schema is built from the migrations once per run, and tables are emptied before each test.
- `tests/helpers.py` has the building blocks: `signup(client)` makes a workspace and returns
  an `Account` (with `.get/.post/.patch` that send its token), `add_staff(owner, ...)`,
  `invite_and_join(owner, role="manager", scope_department_id=...)`.
- Tests read like stories: set up a small company, act, and assert on what each person sees.
  Read `tests/test_leave.py` and `tests/test_tasks.py` as examples.
- Coverage must stay above 85% (it's ~93%).

### 6.2 Browser tests (Playwright)

`web/e2e/*.spec.ts` drive a real Chromium against the production build, on a desktop and a
phone-sized screen. Each test is a user journey (sign up → add staff → staff signs in in
Bangla → clocks in…). `expectAccessible(page, label)` runs [axe](https://github.com/dequelabs/axe-core)
for WCAG 2.2 AA and fails on sideways scrolling; `watchCsp(page)` collects CSP violations.

```bash
cd web
npm run build                       # e2e runs against the built site
npx playwright test                 # starts the API and the site itself (playwright.config.ts)
npx playwright test e2e/leave.spec.ts --project=desktop   # one file, one screen size
npx playwright test --ui            # watch it run, step by step
```

Learn: [Playwright: writing tests](https://playwright.dev/docs/writing-tests) and
[locators](https://playwright.dev/docs/locators) (prefer `getByRole`, `getByLabel`).

### 6.3 `scripts/check.sh`, the rule

It runs everything CI runs: API lint, format, types, module boundaries, migrations in sync,
API tests, the API-contract check, web lint, types, unit tests and build. Add `E2E=1` to
include the browser tests (about 6 minutes):

```bash
./scripts/check.sh            # quick-ish (~6 min)
E2E=1 ./scripts/check.sh      # everything (~12 min)
```

**Only push to `main` when it passes.** CI (`.github/workflows/ci.yml`) runs the same on
every push, plus secret scanning, dependency audit and a container build.

---

## 7. Walkthrough: adding a feature end to end

Say you want **a "notes" field on holidays** (e.g. "Office closed, deliveries continue").
Follow the same steps for anything bigger.

1. **Model**: `api/app/modules/leave/models.py`, in `class Holiday`:
   `notes: Mapped[str | None] = mapped_column(Text)`.
2. **Migration**:
   `uv run alembic revision --autogenerate -m "holiday notes"`, then rename and number it
   like the others; `uv run alembic upgrade head`; `uv run alembic check`.
3. **Schemas**: `leave/schemas.py`: add `notes: str | None = None` to `HolidayIn` (with a
   length limit, like other text fields) and `notes: str | None` to `HolidayOut`.
4. **Service**: `leave/service.py` `add_holiday`: save `body.notes`; include it in the
   `audit.record` data.
5. **Test first, or right after**: in `api/tests/test_leave.py`, add a test that posts a
   holiday with notes and reads it back, and one that a too-long note is refused (422).
   Run `uv run pytest -q tests/test_leave.py`.
6. **Types for the web**: `scripts/gen-api-types.sh` (updates `web/src/api/schema.d.ts`).
7. **UI**: find the holiday form (search the code: `grep -rn "holidays" web/src`), add a
   `<Field label={t("leave.holidayNotes")}><Textarea {...register("notes")} /></Field>`.
8. **Texts**: add `holidayNotes` to both `en.ts` and `bn.ts`.
9. **Browser test**: extend the leave settings journey in `web/e2e/leave.spec.ts` if the
   feature matters to users.
10. **Docs**: a line in `docs/PROGRESS.md` (and the README if users would care).
11. `E2E=1 ./scripts/check.sh`, then commit (`feat(leave): notes on holidays`) and push.

**For a whole new module**, copy the shape of a small one (`announcements/` is a good
template): add it to `catalog.MODULES` (so workspaces can switch it on), register its
permissions in `access.py`, give built-in roles what they need in `BUILTIN_ROLES`, include
its router in `main.py`, its models in `models_registry.py`, its layer in the import-linter
contract, `rls.tenant_table` in the migration, a page under `src/app/(product)/app/<name>`,
and a nav item in `components/nav-items.ts`.

---

## 8. Deploying

Nothing is live yet. The plan (and every command) is in `docs/runbooks/deploy.md`. In short:

- **API** → a Docker image (`api/Dockerfile`) on **Google Cloud Run** (scales to zero, so it's
  cheap at low traffic).
- **Database** → **Neon** (managed Postgres) with the same three roles.
- **Web** → **Cloudflare Pages** serving `web/out`, with `web/functions/v1` proxying `/v1` to
  Cloud Run, so the browser sees one origin (simpler cookies, stricter security).
- **Secrets** → Google Secret Manager; `scripts/gen-keys.sh` makes the signing and
  encryption keys.
- **Scheduled jobs** → Cloud Scheduler (outbox, maintenance, digest, report emails).
- **Backups** → a nightly encrypted dump (`infra/backup`); restoring is in `docs/runbooks/restore.md`.
- `.github/workflows/deploy.yml` deploys on demand once the accounts exist.

Budget target: under $50/month for the first customers.

---

## 9. Cookbook: everyday tasks

| I want to… | Do this |
|---|---|
| See every API endpoint | <http://localhost:8000/docs> |
| Reset my local database | `cd api && uv run alembic downgrade base && uv run alembic upgrade head` |
| Look inside the database | `psql postgresql://cm_owner:cm_owner@localhost:5432/companymgmt` then `\dt`, `SELECT * FROM employees LIMIT 5;` (as the owner role, RLS still applies unless you `SET row_security = off`) |
| See emails the app "sends" | They're printed in the API terminal (`EMAIL_BACKEND=console`) |
| Find where a screen's text comes from | Search the English text in `web/src/i18n/en.ts`, then search the key in `web/src` |
| Find the endpoint a button calls | Browser DevTools → Network tab → click it → look at the `/v1/...` request |
| Find the code for an endpoint | `grep -rn '"/requests"' api/app/modules` (route path), then follow the `service.` call |
| Add a permission | `perms.register(...)` in the module's `access.py`; grant it in `catalog.BUILTIN_ROLES` |
| Add a text in both languages | Same key in `en.ts` and `bn.ts`; `npm run typecheck` tells you if one is missing |
| Change colours/fonts | Tokens in `web/src/app/globals.css` (both light and dark blocks) |
| Run one API test with prints | `uv run pytest -q -s tests/test_x.py -k name --no-cov` |
| Debug a failing browser test | `npx playwright test e2e/x.spec.ts --project=desktop --debug`, or open `test-results/…/trace.zip` with `npx playwright show-trace` |

---

## 10. Troubleshooting

- **`connection refused` on port 5432**: Postgres isn't running: `sudo service postgresql start`.
- **`password authentication failed for user "cm_app"`**: run `scripts/dev-db.sh` again.
- **`relation "…" does not exist`**: run `uv run alembic upgrade head` in `api/`.
- **The web app loads but every call fails**: the API isn't running on port 8000, or you
  opened port 8000 in the browser instead of 3000.
- **Sign-in says "too many attempts"**: you hit a rate limit; wait 5–15 minutes, or for local
  work set `LOGIN_LIMIT_PER_IP=1000` and `SIGNUP_LIMIT_PER_HOUR=1000` in `.env`.
- **`OSError: cannot load library 'libpango…'`**: install Pango (section 1.1); only payslip
  PDFs need it.
- **`check.sh` fails at "web types match the backend"**: you changed the API; run
  `scripts/gen-api-types.sh` and commit the result.
- **`alembic check` says there are new operations**: your models and migrations disagree;
  generate a migration (section 4.5).
- **Playwright can't find a browser**: `npx playwright install chromium` once.
- **`MissingGreenlet` in the API**: you touched a lazy relationship or deferred column in
  async code; load it in the query.

---

## 11. Glossary and learning links

| Term | Meaning here | Learn more |
|---|---|---|
| Tenant / workspace | One company and all its data | [Multi-tenancy](https://en.wikipedia.org/wiki/Multitenancy) |
| RLS | Postgres hides rows of other tenants, enforced by the database | [Row security policies](https://www.postgresql.org/docs/16/ddl-rowsecurity.html) |
| Role / permission / scope | What a member may do, and over which departments | [RBAC](https://en.wikipedia.org/wiki/Role-based_access_control) |
| Module | A feature area a workspace switches on (leave, payroll…) | section 4.2 |
| Modular monolith | One app and one database, split into modules with enforced boundaries | [Modular monolith](https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer) |
| Service function | Where business rules live; routes and capabilities call it | section 4.2 |
| Capability | A described read/write the AI layer can use | section 4.10 |
| Domain event | A record that something happened ("leave.approved") | [Domain events](https://martinfowler.com/eaaDev/DomainEvent.html) |
| Outbox | Side effects saved with the change, sent after commit | [Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html) |
| Migration | A versioned change to the database schema | [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html) |
| ETag / If-Match | Version checks that stop two people overwriting each other | [MDN: If-Match](https://developer.mozilla.org/docs/Web/HTTP/Reference/Headers/If-Match) |
| Problem details | The standard JSON shape for API errors | [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) |
| OpenAPI | The machine-readable API description the web types are generated from | [OpenAPI](https://learn.openapis.org/) |
| JWT / EdDSA | Signed access tokens | [jwt.io](https://jwt.io/introduction) |
| Argon2id | The password hashing algorithm | [OWASP cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) |
| TOTP / MFA | Six-digit codes from an authenticator app | [RFC 6238](https://www.rfc-editor.org/rfc/rfc6238) |
| CSP | Browser rule listing which scripts may run | [MDN: CSP](https://developer.mozilla.org/docs/Web/HTTP/Guides/CSP) |
| CORS | Which other sites may call the API from a browser | [MDN: CORS](https://developer.mozilla.org/docs/Web/HTTP/Guides/CORS) |
| WCAG / axe | Accessibility standard and the tool that checks it | [WCAG 2.2 overview](https://www.w3.org/WAI/standards-guidelines/wcag/) |
| ASVS | OWASP's application security checklist (we target level 2) | [ASVS](https://owasp.org/www-project-application-security-verification-standard/) |
| Static export | Next.js built into plain files, no server | [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports) |
| Query key / invalidation | How TanStack Query caches and refreshes data | [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys) |
| Conventional commits | `feat:`, `fix:`, `docs:`… commit messages | [conventionalcommits.org](https://www.conventionalcommits.org/) |
| Cloud Run / Neon / Cloudflare Pages | Where the API, database and web will run | [Cloud Run](https://cloud.google.com/run/docs/overview/what-is-cloud-run), [Neon](https://neon.com/docs/introduction), [Pages](https://developers.cloudflare.com/pages/) |
| OpenTofu | Infrastructure as code (open Terraform) | [OpenTofu docs](https://opentofu.org/docs/intro/) |

General foundations, if any of these feel shaky:
[MDN: how the web works](https://developer.mozilla.org/docs/Learn_web_development/Getting_started/Web_standards/How_the_web_works),
[HTTP overview](https://developer.mozilla.org/docs/Web/HTTP/Guides/Overview),
[SQL tutorial (PostgreSQL)](https://www.postgresqltutorial.com/),
[Git: the simple guide](https://rogerdudler.github.io/git-guide/) and the
[Pro Git book](https://git-scm.com/book/en/v2).

---

## 12. A study plan

Two to three weeks, an hour or two a day:

1. **Day 1–2: run it.** Section 1. Create a workspace, add staff, clock in, ask for and
   approve leave, run payroll. Run `scripts.agency_week` and click around the Reports page.
   Open <http://localhost:8000/docs> and try a few endpoints.
2. **Day 3–5: Python backend basics.** The FastAPI tutorial (first 10 chapters), then read
   `api/app/main.py`, `core/errors.py`, `platform/deps.py` (`allow`, `Ctx`).
3. **Day 6–7: one module end to end.** Read `announcements/` top to bottom (models →
   schemas → access → service → routes → capabilities), then `tests/test_announcements.py`.
   Then `web/src/app/(product)/app/announcements/page.tsx` and `components/announcements/`.
4. **Day 8–9: data and safety.** SQLAlchemy quickstart; read `core/models.py`, `core/db.py`,
   `migrations/rls.py`, one migration; run `tests/test_isolation.py` and read what it checks.
5. **Day 10–12: frontend.** React "Learn", then TanStack Query overview; read
   `src/api/client.ts`, `src/auth/session.tsx`, `components/app-shell.tsx`,
   `components/ui/field.tsx`, and one form (`components/tasks/project-dialog.tsx`).
6. **Day 13–14: tests.** Write one small API test and one Playwright test of your own. Run
   `E2E=1 ./scripts/check.sh`.
7. **Then:** do the holiday-notes walkthrough (section 7) for real, on a branch, as practice.

Keep `docs/PROGRESS.md` open while you work: it records why things are the way they are.
