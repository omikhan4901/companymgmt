# 13. Reference

## 13.1 Settings (environment variables)

Read by `api/app/core/config.py` from the environment or `.env` (repo root). In
production they come from Cloud Run env vars and Secret Manager (**S** = keep it secret).

| Variable | Default | Meaning |
|---|---|---|
| `ENV` | `dev` | `dev`, `test`, `staging`, `prod`. Staging/prod refuse to start without keys, with a console/memory email backend, or with the fake AI; they hide `/docs` and add HSTS |
| `DATABASE_URL` **S** | local `cm_app` | the API's connection: `postgresql+psycopg://cm_app:…@host/companymgmt?sslmode=verify-full&sslrootcert=system` (Neon: the **pooled** address) |
| `MIGRATIONS_DATABASE_URL` **S** | local `cm_owner` | migrations and the maintenance job (Neon: the **direct** address) |
| `APP_DB_ROLE` | `cm_app` | the role migrations grant to |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | 5, 5 | connections per instance |
| `WEB_BASE_URL` | `http://localhost:3000` | links in emails |
| `CORS_ORIGINS` | `http://localhost:3000` | comma-separated browser origins |
| `JWT_PRIVATE_KEY` **S** | generated per process in dev | Ed25519 PEM for access tokens (`scripts/gen-keys.sh`) |
| `JWT_PUBLIC_KEY` | derived | optional |
| `JWT_ISSUER`, `JWT_AUDIENCE` | `companymgmt`, `companymgmt-web` | token claims |
| `ACCESS_TOKEN_MINUTES` | 10 | access token life |
| `REFRESH_IDLE_DAYS`, `REFRESH_ABSOLUTE_DAYS` | 7, 30 | session limits |
| `REFRESH_REUSE_GRACE_SECONDS` | 10 | two tabs refreshing at once isn't theft |
| `STEP_UP_MINUTES` | 5 | how recent a sign-in sensitive actions need |
| `SIGNUP_LIMIT_PER_HOUR` | 10 | new workspaces per IP per hour |
| `LOGIN_LIMIT_PER_IP` | 30 | sign-ins per IP per 5 minutes |
| `FIELD_ENCRYPTION_KEYS` **S** | zero key in dev | JSON `{"k1": "<base64 32 bytes>"}`; **back it up** |
| `FIELD_ENCRYPTION_ACTIVE_KID` | `k1` | which key encrypts new values |
| `EMAIL_BACKEND` | `console` | `console` (print), `memory` (tests), `smtp` |
| `SMTP_URL` **S** | — | `smtps://user:pass@host:465` |
| `MAIL_FROM` | `CompanyMgmt <no-reply@localhost>` | sender |
| `SUPPORT_EMAIL` | — | where "Contact support" goes (empty: logged only) |
| `TURNSTILE_SECRET` **S** | — | Cloudflare Turnstile; empty disables the challenge |
| `CAPTCHA_AFTER_FAILURES` | 5 | failed sign-ins before the challenge |
| `INTERNAL_TOKEN` **S** | — | `X-Internal-Token` for `/internal/*`; empty disables them |
| `TRUST_PROXY_HEADERS` | `false` (`true` in the image) | read the client IP from `X-Forwarded-For` |
| `PROXY_TOKEN` **S** | — | shared with the Pages Function; when set, `/v1` only works through it |
| `SENTRY_DSN` **S** | — | optional error reporting |
| `AI_PROVIDER` | — | empty = Gemini when a key is set; `fake` for dev/test |
| `GEMINI_API_KEY` **S** | — | switches the assistant on (paid tier) |
| `GEMINI_MODEL`, `GEMINI_EMBED_MODEL` | `gemini-2.5-flash`, `gemini-embedding-001` | models |
| `GEMINI_BASE_URL` | Google's v1beta | for proxies/tests |
| `PLATFORM_OPERATORS` | — | comma-separated emails allowed into Settings → Platform |

Web build variables: `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`,
`NEXT_TELEMETRY_DISABLED=1`; development only: `DEV_API_ORIGIN`. Pages Function:
`API_ORIGIN`, `PROXY_TOKEN`.

## 13.2 Scripts

| Command | Does |
|---|---|
| `scripts/check.sh` | the full gate (add `E2E=1` for browser tests) |
| `scripts/dev-db.sh` | local roles and databases |
| `scripts/gen-api-types.sh` | OpenAPI → `web/src/api/openapi.json` and `schema.d.ts` |
| `scripts/gen-keys.sh` | production keys and the internal token |
| `cd api && uv run python -m scripts.demo_seed` | a demo tea house |
| `cd api && uv run python -m scripts.agency_week` | a 30-person agency's week |
| `cd api && uv run python -m scripts.api_contract check|accept` | public API breaking-change check / accept a new snapshot |
| `cd api && uv run python -m app.jobs.maintenance` | the nightly purge job |
| `cd web && npm run serve` | serve the static build like Cloudflare |

## 13.3 Permissions

† = scoped (limited to the member's department subtree when one is set); * = owner only.

| Area | Permissions |
|---|---|
| Platform | `workspace.manage`, `workspace.delete`*, `workspace.export`*, `workspace.import`*, `billing.manage`*, `members.view`, `members.invite`, `members.manage`, `roles.manage`, `branches.manage`, `audit.view`, `developers.manage`, `automations.manage`, `ai.use`, `ai.manage` |
| People | `people.view`†, `people.manage`†, `departments.manage`, `reports.view`† |
| Attendance | `attendance.self`, `attendance.view`†, `attendance.manage`†, `attendance.approve`†, `attendance.export`† |
| Leave | `leave.self`, `leave.view`†, `leave.approve`†, `leave.manage`†, `leave.settings` |
| Payroll | `payroll.self`, `payroll.view`†, `payroll.manage`, `payroll.run`, `payroll.approve` |
| Tasks | `tasks.self`, `tasks.manage`† |
| Announcements | `announcements.read`, `announcements.post`† |
| Documents | `documents.read`, `documents.manage` |
| Sales | `sales.sell`, `sales.view`, `sales.manage` |
| Customers | `customers.view`, `customers.manage` |
| Expenses | `expenses.record`, `expenses.manage` |
| Inventory | `inventory.view`, `inventory.manage` |
| Accounting | `accounting.view`, `accounting.manage` |

Live list: `GET /v1/permissions`. Built-in role grants: `catalog.BUILTIN_ROLES`. A till PIN
session keeps only `sales.sell`, `customers.view`, `customers.manage`, `expenses.record`.

## 13.4 Domain events and who listens

| Event | Emitted by | In-transaction listeners | After-commit listeners |
|---|---|---|---|
| `member.joined`, `member.removed` | platform | onboarding auto-start, automations | webhooks |
| `attendance.correction_requested/approved/rejected` | attendance | notifications | webhooks (approved), automations |
| `leave.requested/approved/rejected/cancelled` | leave | notifications | webhooks, automations |
| `payroll.submitted`, `payroll.finalized` | payroll | notifications | accounting (finalized), webhooks, automations |
| `task.assigned/completed/commented`, `project.members_added` | tasks | notifications | webhooks (assigned), automations |
| `announcement.published` | announcements | notifications | webhooks, automations |
| `document.published`, `document.acknowledged` | documents | notifications; onboarding ticks | webhooks, automations |
| `sale.completed/returned/voided` | sales | inventory (stock moves) | accounting, webhooks |
| `sales.drawer_closed` | sales | — | webhooks |
| `customer.paid`, `customer.adjusted` | customers | — | accounting, webhooks (paid) |
| `expense.recorded/changed/deleted/petty_top_up` | expenses | — | accounting, webhooks (recorded) |
| `purchase.received`, `supplier.paid`, `stock.moved` | inventory | — | accounting, webhooks |
| `stock.low` | inventory | notifications | webhooks |
| `ai.allowance_changed` | ai/operator | notifications | — |
| `automation.message` | automations | — | — |
| `webhook.disabled` | webhooks | — | — |

Public webhook names (the catalogue in `platform/webhooks.py`): `employee.onboarded`,
`employee.offboarded`, `leave.requested`, `leave.approved`, `leave.rejected`,
`leave.cancelled`, `attendance.corrected`, `task.assigned`, `document.published`,
`announcement.published`, `payroll.finalized`, `sale.completed`, `sale.returned`,
`sale.voided`, `drawer.closed`, `customer.paid`, `expense.recorded`, `purchase.received`,
`supplier.paid`, `stock.low`.

## 13.5 Internal endpoints and jobs

| Endpoint / job | Schedule (cheapest, chapter 10.3) |
|---|---|
| `POST /internal/outbox/dispatch` | `*/30 * * * *` |
| `POST /internal/automations/tick` | `*/30 * * * *` |
| `POST /internal/webhooks/tick` | only once webhooks are used; up to every minute |
| `POST /internal/maintenance/daily` | daily |
| `POST /internal/notifications/digest` | daily, morning, Asia/Dhaka |
| `POST /internal/reports/send` | daily, Asia/Dhaka |
| Cloud Run job `companymgmt-maintenance` (`python -m app.jobs.maintenance`) | nightly (OpenTofu) |
| Cloud Run job `companymgmt-backup` (`infra/backup`) | nightly (OpenTofu) |
| Cloud Run job `companymgmt-migrate` (`alembic upgrade head`) | each deploy |

All need `X-Internal-Token` (the Cloud Run jobs don't; they're started by the scheduler's
service account).

## 13.6 HTTP status codes and common error codes

Every error is `application/problem+json`:
`{"type", "title", "status", "detail", "code", "errors": [{"field", "message"}]}`.

| Status | Means | Common `code`s |
|---|---|---|
| 400 | bad request | `bad_cursor`, `import_format` |
| 401 | not signed in / session gone | `session_ended`, `token_expired`, `bad_credentials`, `api_key_invalid`, `api_key_revoked` |
| 402 | the plan or workspace state doesn't allow it | `module_off`, `module_over_limit`, `workspace_read_only`, `api_not_in_plan`, `feature_not_in_plan`, `people_limit`, `branch_limit`, `module_limit`, `ai_not_in_plan`, `ai_allowance_used` |
| 403 | signed in, not allowed | `forbidden`, `not_member`, `no_workspace`, `mfa_setup_required`, `reauth_required`, `ip_not_allowed`, `sso_required`, `till_session`, `password_change_required`, `escalation`, `owner_only`, `self_approval`, `api_key_not_allowed`, `outside_area`, `direct_access` |
| 404 | not found **or not yours** | `not_found` |
| 409 | conflicts with the current state | `already_decided`, `already_clocked_in`, `not_clocked_in`, `drawer_open`, `drawer_closed`, `overlap`, `not_enough_balance`, `credit_limit`, `period_locked`, `slug_taken`, `name_taken`, `last_owner`, `already_void` |
| 410 | gone | `workspace_deleted` |
| 412 / 428 | stale or missing `If-Match` | `precondition_failed`, `precondition_required` |
| 413 | too large | `too_large`, `file_too_large` |
| 422 | validation | `validation_error` with `errors[]` |
| 429 | rate limited (`Retry-After`) | `too_many`, `captcha_required` |
| 503 | a dependency is off | `ai_unavailable`, `ai_off` |

The web app translates some codes into friendlier text (`web/src/lib/errors.ts`).

## 13.7 Where things are

| Looking for… | Look in |
|---|---|
| A route | `grep -rn '"/requests"' api/app` (its path), then follow `service.` |
| A screen's text | search the English in `web/src/i18n/en.ts`, then its key in `web/src` |
| The call a button makes | browser DevTools → Network → the `/v1/…` request |
| A table's definition | `grep -rn '__tablename__ = "x"' api/app` |
| When a table changed | `grep -rln '"x"' api/migrations/versions` |
| Why something is the way it is | `docs/PROGRESS.md` (decisions), `docs/IMPLEMENTATION_PLAN.md` §12 (what each milestone did) |

## 13.8 Glossary

| Term | Meaning here | Learn more |
|---|---|---|
| Workspace / tenant | one company and all its data | [Multi-tenancy](https://en.wikipedia.org/wiki/Multitenancy) |
| RLS | Postgres hides other tenants' rows, enforced by the database | [Row security](https://www.postgresql.org/docs/16/ddl-rowsecurity.html) |
| Role / permission / scope | what a member may do, and over which departments | [RBAC](https://en.wikipedia.org/wiki/Role-based_access_control) |
| Module | a feature area a workspace switches on | chapter 1.3 |
| Modular monolith | one app and database, split into modules with enforced boundaries | [primer](https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer) |
| Service | where business rules live; routes, capabilities and jobs call it | chapter 4.5 |
| Capability | a typed read/write the AI may use, run as the asker | chapter 3.10 |
| Domain event | a record that something happened (`leave.approved`) | [Fowler](https://martinfowler.com/eaaDev/DomainEvent.html) |
| Outbox | side effects saved with the change, delivered after commit | [pattern](https://microservices.io/patterns/data/transactional-outbox.html) |
| Migration | a versioned schema change | [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html) |
| ETag / If-Match | version checks that stop overwrites | [MDN](https://developer.mozilla.org/docs/Web/HTTP/Reference/Headers/If-Match) |
| Idempotency key | lets a client retry a write safely | [IETF draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/) |
| Problem details | the JSON error format | [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) |
| OpenAPI | the machine-readable API description | [OpenAPI](https://learn.openapis.org/) |
| JWT / EdDSA | signed access tokens | [jwt.io](https://jwt.io/introduction) |
| Argon2id | password hashing | [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) |
| TOTP | six-digit codes from an authenticator app | [RFC 6238](https://www.rfc-editor.org/rfc/rfc6238) |
| Passkey / WebAuthn | phishing-resistant sign-in with the device | [passkeys.dev](https://passkeys.dev/) |
| OIDC / SSO | sign-in with a company identity provider | [OpenID Connect](https://openid.net/developers/how-connect-works/) |
| SCIM | provisioning users from a directory | [RFC 7644](https://www.rfc-editor.org/rfc/rfc7644) |
| Webhook | an HTTP call to a customer's server when something happens | [Standard Webhooks](https://www.standardwebhooks.com/) |
| SSRF | tricking a server into calling internal addresses | [OWASP](https://owasp.org/www-community/attacks/Server_Side_Request_Forgery) |
| CSP | the browser's list of allowed scripts | [MDN](https://developer.mozilla.org/docs/Web/HTTP/Guides/CSP) |
| WCAG / axe | accessibility standard / checker | [WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/) |
| ASVS | OWASP's security checklist (level 2) | [ASVS](https://owasp.org/www-project-application-security-verification-standard/) |
| Static export | Next.js built into plain files | [Next.js](https://nextjs.org/docs/app/guides/static-exports) |
| Weighted average cost | stock valued at the average price paid | [Wikipedia](https://en.wikipedia.org/wiki/Average_cost_method) |
| Double-entry | every posting's debits equal its credits | [Wikipedia](https://en.wikipedia.org/wiki/Double-entry_bookkeeping) |
| Scale to zero | no running servers (or cost) when idle | [Cloud Run](https://cloud.google.com/run/docs/about-instance-autoscaling) |
