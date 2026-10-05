# Not yet tested

Since 2026-10-04 the owner asked for speed: code and unit tests are written, but only lint
and type checks are run locally. CI runs the tests on GitHub and may be red until a
test-and-fix pass. Everything below needs that pass: run `./scripts/check.sh` with
`E2E=1`, fix what breaks, then delete the entry.

**The CI workflow is switched off on GitHub** (owner, 2026-10-04). Turn it back on for
the test-and-fix pass: Actions → CI → Enable workflow (or
`gh api -X PUT repos/omikhan4901/companymgmt/actions/workflows/371331708/enable`).
CodeQL, Deploy and Dependabot are still on.

Last fully green commit: `86be8ac` (M6 done, all API, web and browser tests passing).

## M7 AI actions and automation

- [ ] **Actions (propose → confirm).** New write capabilities `tasks.update`,
  `tasks.comment`, `leave.decide`, `announcements.post`; `ai_proposals` table (migration
  0017); `app/ai/actions.py`; confirm/cancel routes; action cards on the Ask page.
  Unit tests written in `api/tests/test_ai.py` (`test_actions_*`, `test_staff_cant_be_talked_*`)
  and the isolation test, never run. No browser test yet.
- [ ] **Writing help.** `POST /v1/ai/write` (draft, improve, shorter, translate) and
  `POST /v1/ai/documents/{id}/summary`; `app/ai/writing.py`; `documents.readable_text`;
  "Help me write" menu in the announcement and new-task dialogs; "Summarise" on documents.
  Writing and summaries now count towards the monthly allowance. Tests
  `test_writing_help_*` and `test_document_summaries_*` written, never run.
- [ ] **Automations (API).** New module `app/modules/automations` (schedule or event
  triggers, conditions, notify / create-task actions, recipients incl. overdue tasks and
  not clocked in), engine with rate limits, auto-pause, loop guard (`events.origin`),
  `member.joined` event, `/internal/automations/tick` (Cloud Scheduler job added to the deploy runbook), migration 0018, AI drafting
  `POST /v1/ai/automations/draft`. Tests in `api/tests/test_automations.py` and the
  isolation test, never run; migration applied locally only.
- [ ] **Automations (web).** `/app/automations`: list, switch, run now, history, editor
  (schedule/event, conditions, notify/create-task steps, recipient picker), starter
  templates, "Describe what you want" (AI draft). Nav item for `automations.manage`.
  No browser test yet; never opened in a browser.
- [ ] **Early-warning signals.** `app/modules/reports/signals.py` (attendance drop by
  department, projects slipping or due, heavy workloads when `signal_people` is on),
  `GET /v1/reports/signals`, dismiss for 30 days, migration 0019 (`signal_dismissals`,
  `ai_settings.signal_people`); "Needs a look" card on Reports; people-signals switch in
  AI settings. Tests in `api/tests/test_signals.py` never run; the attendance-drop signal
  has no test at all (needs attendance history seeded); performance with many
  departments unmeasured (two overview reports per department).

## M8 Shop pack

- [ ] **Shop API.** New modules `sales` (catalogue, categories, tax rates the workspace
  defines incl. compound and inclusive/exclusive prices, shop settings, cash drawer
  open/close with expected vs counted cash, sales with idempotent `client_id` for
  offline tills, returns, voids, receipts, period summary with tax totals), `customers`
  (dues ledger, credit limits, payments, adjustments, statements) and `expenses`
  (categories seeded on enable, receipt photos checked by file signature, petty cash
  top-ups, drawer expenses counted at drawer close). Migration 0020. Capabilities
  `sales.summary`, `customers.list`. Built-in roles got sales/customers/expenses
  permissions. Tests: `test_tax.py` (incl. a Hypothesis property), `test_shop.py`,
  parity and isolation additions — none run. Check: the isolation test now switches on
  seven modules (may exceed a plan's module limit); workspace export of
  `expenses.receipt` bytes and `sale_lines` JSON not checked.
- [ ] **Shop web.** `/app/pos` (open/close drawer, item buttons by category, other
  items, cart, customer on credit, cash and change, offline queue in localStorage
  synced every 15 s), `/app/sales/receipt?id=` (80 mm receipt, browser print; app chrome
  hidden with `print:`), `/app/sales` (sales by day with returns and voids, period
  summary with tax table and print, items and categories, taxes and receipt settings,
  drawers), `/app/customers` (dues list, statement, payments, adjustments, WhatsApp
  reminder, print), `/app/expenses` (month view, receipt photo upload, petty cash).
  Nav items. `lib/whatsapp.test.ts` written, not run. Never opened in a browser; no
  e2e. Known gaps: a sale the server refuses while syncing stays in the offline queue
  with no screen to fix it; cashier PINs (from the plan) not built.

## M9 Inventory and accounting

- [ ] **Inventory API.** `app/modules/inventory`: stock items (opt-in tracking, reorder
  level), levels per branch, movement ledger with weighted average cost
  (`costing.py`), opening stock, adjustments, purchases with input tax and supplier
  balances, supplier payments, transfers, counts, low-stock events and notifications.
  Stock follows `sale.completed` / `sale.returned` / `sale.voided` in the same
  transaction. Migration 0021. Capability `inventory.stock`.
- [ ] **Accounting API.** `app/modules/accounting`: starting chart with roles, posting
  rules (`postings.py`), automatic postings after commit via the outbox for sales,
  returns, voids, stock, purchases, supplier and customer payments, dues adjustments,
  expenses (incl. changes, deletes, petty cash) and payroll; idempotent backfill on
  enable and on demand; manual entries, reversal, period lock; trial balance, P&L,
  balance sheet, ledger, cash book; tax-return templates built by the workspace and
  filled per period. Capability `accounting.profit_and_loss`.
- [ ] Tests written, never run: `test_ledger.py` (Hypothesis: postings balance,
  stock reconciles), `test_books.py` (end to end incl. tax return boxes), parity and
  isolation additions. Expected amounts in `test_books.py` were worked by hand; check
  them carefully when they first run. Unverified: the outbox delivers `later`
  subscribers for these events in tests (`outbox.dispatch()`), and postings for an
  event whose module was switched on later are picked up by backfill.
- [ ] **Inventory and accounts web.** `/app/inventory` (stock with low filter, track an
  item / opening stock / adjust / reorder level, receive purchases with input tax,
  suppliers and payments, stock count) and `/app/accounting` (P&L, balance sheet,
  trial balance with print; journal with hand entries and reversal; cash book; chart
  of accounts with ledgers; tax-return template editor and filling; settings: lock
  date, tax and expense-category account mapping, backfill). Nav items. Not built
  with `next build` locally; never opened in a browser.


## M10 Enterprise and developer platform

- [ ] **Easy onboarding.** Workspace addresses (`PUT /v1/workspace/address`, owner
  only; reserved and look-alike names refused; old addresses kept by `previous_slugs`
  and never reused; `GET /v1/public/workspace`), join links (`/v1/join-links`, public
  `/v1/join/lookup` and `/v1/join` creating a staff account), first-day checklist and
  sample data (`app/modules/welcome`), migration 0022. Web: `/join` page, Team →
  Join links (QR code on a canvas, copy, WhatsApp share), home checklist card with
  sample data, Settings → address card, login page reads the workspace from
  `<slug>.<NEXT_PUBLIC_WORKSPACE_DOMAIN>`. Tests: `test_onboarding.py`,
  `lib/address.test.ts`, isolation addition — none run. Needs the owner: wildcard DNS
  and Pages custom domains for `*.companymgmt.app`, and API CORS for those origins.
- [ ] **API keys.** `/v1/api-keys` (create with chosen permissions, rate per minute,
  allowed networks, expiry; edit; rotate with a grace period; revoke; daily usage;
  grantable permissions), `cmk_<workspace>_<secret>` keys accepted by every `allow()`
  route in `deps.py` (permissions = key's ∩ maker's now, minus owner-only; plan feature
  `api`; account routes refuse keys), new permission `developers.manage`, migration
  0023. `tests/test_developers.py` **was run once and passed (12 tests)**; the full
  suite wasn't, so other tests may notice the new permission or tables (isolation test
  has no API key / webhook ids yet; route-access audit not run).
- [ ] **Workspace network allowlist.** `GET/PUT /v1/workspace/ip-allowlist` (owner,
  plan feature `sso`, refuses lists that leave the owner out), enforced in
  `_bind_workspace` for people and keys. Covered by the run above.
- [ ] **Idempotency-Key.** `app/core/idempotency.py` (pure ASGI, 24 h, per API key or
  session, 409 while running, 422 on reuse, 5xx not kept), table `idempotency_keys`,
  daily clean-up. Covered by the run above; not tried with file uploads or streaming.
- [ ] **Signed webhooks.** `app/modules/platform/webhooks.py` (public catalogue with
  thin payloads, HMAC signatures, backoff 1 m → 24 h over 8 tries, endpoint switched
  off after 40 failures in a row, DNS-pinned HTTPS to public addresses only) and
  `/v1/webhooks` routes (CRUD, roll secret, test ping, delivery log, resend),
  `/internal/webhooks/tick` (Cloud Scheduler job added to the runbook), new
  `member.removed` event. Covered by the run above with a mock transport; never sent
  to a real server (SNI pinning via `sni_hostname` unverified against real TLS).
- [ ] **Company sign-in (OIDC SSO), own AI key, audit export.** `app/modules/platform/sso.py`
  (PKCE + state + nonce, ID token checked against the provider's published keys,
  auto-join, "require company sign-in" enforced in `_bind_workspace` via
  `auth_sessions.method`), `app/core/safehttp.py` (shared SSRF-safe client, now also
  used by webhooks), `PUT/DELETE /v1/ai/own-key`, `GET /v1/audit/export` (JSONL/CSV with
  the hash chain), migration 0024. `tests/test_sso.py` **run once and passed (6 tests)**
  against a pretend provider; never tried with a real Google/Entra/Okta tenant.
- [ ] **SCIM 2.0 and sandbox workspaces.** `app/modules/platform/scim.py` (`/scim/v2`
  Users with filter, create, replace, Okta- and Entra-style PATCH, delete; owner
  protected; API key needs members.invite + members.manage; plan feature `sso`),
  `memberships.external_id`, `POST /v1/workspace/sandbox` (`tenants.sandbox_of`, same
  plan, never billed), migration 0025. `tests/test_scim.py` **run once and passed (4)**.
  Not tried against a real Okta/Entra app; SCIM doesn't check the plan's people limit.
- [ ] **API contract, SDKs, developer docs.** `api/scripts/api_contract.py` + snapshot
  `docs/api/openapi-v1.json` (step in `check.sh`), `http.deprecated()` helper (unused so
  far), `GET /v1/members/{id}`, `docs/api/README.md`, `sdk/typescript`, `sdk/python`.
  Contract tests and both SDKs' unit tests **were run and pass**; the SDKs were never
  pointed at a running server.
- [ ] **Developer and security screens (web).** Settings → Developers (API keys: create
  with permission picker, show once, usage chart, rotate, revoke; webhooks: editor with
  event picker, signing secret shown once, test, delivery log, resend, delete; sandbox),
  Settings → Security (company sign-in, network allowlist, own AI key), audit export
  button, login "Sign in with your company account", `/sso/callback`, `sandbox` on the
  session workspace. Types and lint pass; never opened in a browser; no e2e test.

## M11 Security hardening

- [ ] **Till PINs on registered devices.** `app/modules/sales/tills.py` (register/revoke
  tills, own PIN with weak-PIN refusal, `/v1/till` and `/v1/till/unlock` with the
  `X-Till-Token` header, 5 wrong PINs → 15 min lock, PIN sessions limited to selling and
  12 hours, account changes refused, revoking a till ends its sessions), migration
  0026. `tests/test_tills.py` **run once and passed (3)**. Web: Sales → Tills, Account →
  Till PIN, `/till` PIN pad, "Lock till" on the POS. Never opened in a browser.
- [ ] **Passkeys (WebAuthn).** `app/modules/platform/passkeys.py` (register with step-up,
  list, remove; discoverable passwordless sign-in counting as two-step; single-use
  5-minute challenges; RP id = web domain, workspace subdomains accepted as origins;
  sign-count clone detection), tables `passkeys`, `webauthn_challenges` (migration
  0027), dependency `webauthn` + `@simplewebauthn/browser`. `tests/test_passkeys.py`
  (software authenticator) **run once and passed (2)**. Web: Account → Passkeys, login
  "Sign in with a passkey". Never tried with a real phone or security key.
