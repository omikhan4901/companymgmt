# Not yet tested

Since 2026-10-04 the owner asked for speed: code and unit tests are written, but only lint
and type checks are run locally. CI runs the tests on GitHub and may be red until a
test-and-fix pass. Everything below needs that pass: run `./scripts/check.sh` with
`E2E=1`, fix what breaks, then delete the entry.

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
