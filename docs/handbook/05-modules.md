# 5. Every module

For each module: what it's for, its tables, the rules that matter, its routes, the events
it emits, and its permissions. Paths are under `api/app/modules/<module>/`; the screens are
under `web/src/app/(product)/app/<page>/` with components in `web/src/components/<area>/`.
Full endpoint details: <http://localhost:8000/docs> while the API runs.

Contents: [platform](#51-platform) · [people](#52-people) · [attendance](#53-attendance) ·
[leave](#54-leave) · [payroll](#55-payroll) · [tasks](#56-tasks-and-onboarding) ·
[announcements](#57-announcements) · [documents](#58-documents) ·
[notifications](#59-notifications) · [approvals](#510-approvals) ·
[reports](#511-reports-and-signals) · [imports](#512-imports) · [privacy](#513-privacy) ·
[sales](#514-sales-and-tills) · [customers](#515-customers-and-dues) ·
[expenses](#516-expenses) · [inventory](#517-inventory) · [accounting](#518-accounting) ·
[automations](#519-automations) · [welcome](#520-welcome) · [AI](#521-the-ai-assistant)

---

## 5.1 Platform

Accounts, workspaces, members, roles, branches, plans, the audit log, and the developer
platform. Files are described in chapter 4.4.

**Tables (global):** `users`, `tenants`, `plans`, `auth_sessions`, `refresh_tokens`,
`auth_challenges`, `recovery_codes`, `email_tokens`, `auth_events`, `passkeys`,
`webauthn_challenges`, `sso_states`, `rate_limits`, `idempotency_keys`, `outbox_events`.
**Tables (tenant):** `subscriptions`, `roles`, `memberships`, `invites`, `join_links`,
`branches`, `api_keys`, `api_key_usage`, `webhook_endpoints`, `webhook_deliveries`,
`sso_connections`, `audit_events`, `audit_anchors`, `domain_events`.

**Rules that matter**

- Sign-up creates the user, the workspace (with a unique slug), a Growth trial, the
  built-in roles, the owner membership, a People profile and the preset modules' seed data,
  in one transaction.
- Nobody can grant a permission they don't hold (roles, API keys, invites). Owner-only
  permissions can't be given to anyone else.
- The last owner can't be removed or demoted.
- Staff accounts (no email) sign in with the workspace code + username, and must choose
  their own password at first sign-in. Managers reset them.
- Branches have a time zone, an address and a location area (centre + radius) for
  clock-ins.
- Switching modules respects dependencies and the plan's limit; over the limit a module
  becomes read-only (`locked_modules`), never hidden.
- Deleting a workspace needs a recent sign-in (step-up); it can be restored by the owner
  for 30 days; then the maintenance job erases it and emails a signed certificate.
- Every change to access is in the audit log; `GET /v1/audit/verify` re-checks the hash
  chain.

**Developer platform** (Business plan and up; SSO/SCIM on Enterprise):
API keys (`cmk_…`, chosen permissions, rate limit, network ranges, expiry, rotation with
a grace period, daily usage); webhooks (HMAC-SHA256 signed, thin payloads, retries for
~1.5 days, disabled after 40 failures, delivery log, resend, test); company sign-in
(OIDC); SCIM 2.0; network allowlist; audit export; sandbox workspaces; a workspace's own
Gemini key. The customer-facing guide is `docs/api/README.md`.

**Events:** `member.joined`, `member.removed`, `webhook.disabled`.
**Permissions:** `workspace.manage`, `workspace.delete`*, `workspace.export`*,
`workspace.import`*, `billing.manage`*, `members.view`, `members.invite`,
`members.manage`, `roles.manage`, `branches.manage`, `audit.view`, `developers.manage`,
`ai.use`, `ai.manage`, `automations.manage` (* owner only).
**Screens:** `/app/team`, `/app/settings` (tabs: workspace, modules, branches, roles,
AI, developers, security, data, platform), `/app/account`, sign-in pages.

## 5.2 People

Profiles and the department tree. Always on.

**Tables:** `employees` (one per member, plus people without accounts), `departments`
(a tree via `parent_id`).
**Rules:** a member's profile is created automatically and counts towards the plan's
people limit. National ID numbers are encrypted (AES-GCM, bound to the row). Scoped
permissions reach a department and everything below it; `people/access.py` has
`scope_departments(ctx)` and `in_scope(ctx, id)` that every other module uses.
**Routes:** `/v1/people`, `/v1/people/{id}`, `/v1/people/me`, `/v1/departments`,
`/v1/people/import` (the spreadsheet import, chapter 5.12).
**Permissions:** `people.view`†, `people.manage`†, `departments.manage`, `reports.view`†
(† scoped).
**Screens:** `/app/people`.

## 5.3 Attendance

Clock in and out from a phone, checked against the branch's location.

**Tables:** `attendance_settings`, `attendance_records`, `attendance_corrections`.
**Rules:**
- Location mode per workspace: `off`, `record` (save and flag) or `require` (refuse
  outside the branch area; the default). Clock-**out** is never blocked. Positions are
  saved only at clock-in and clock-out, rounded to ~11 m, with accuracy and distance.
  `geo.py` does the maths (haversine, accuracy allowance).
- A shift belongs to the business date it **started** in the branch's time zone (overnight
  shifts work). A shift open more than 24 hours can't be clocked out: the person asks for a
  fix, and the shift is set aside until approved.
- Corrections ("I forgot to clock out") go to whoever has `attendance.approve` in that
  person's department; nobody approves their own.
- Timesheets per person per day; CSV export protected against formula injection.
- Lateness: "working day starts at" and a grace period (used by reports).
**Routes:** `/v1/attendance/clock-in`, `clock-out`, `status`, `present`, `records`,
`corrections`, `timesheet`, `export.csv`, `settings`.
**Events:** `attendance.correction_requested`, `…_approved`, `…_rejected`.
**Permissions:** `attendance.self`, `attendance.view`†, `attendance.manage`†,
`attendance.approve`†, `attendance.export`†.
**Screens:** `/app/attendance` (and the big button on Home).

## 5.4 Leave

**Tables:** `leave_policies` (work week, accrual style), `leave_types`, `holidays`,
`leave_requests`, `leave_adjustments`.
**Rules:**
- Balances are worked out, not stored: entitlement (pro-rated for mid-year joiners, or
  monthly accrual) + carry-over + adjustments − approved days. `GET /v1/leave/quote`
  shows the day count before asking (days off and holidays don't count).
- Bangladesh workspaces start near the Labour Act 2006: casual, sick, earned, maternity;
  Friday off (`defaults.py`).
- Approval re-checks the balance; nobody approves their own request.
- Colleagues see **that** someone is away on the calendar, not **why**.
- Statuses: `pending → approved | rejected | cancelled`.
**Routes:** `/v1/leave/types`, `policy`, `holidays`, `balances`, `balances/team`, `quote`,
`requests` (+ `approve`, `reject`, `cancel`), `calendar`, `adjustments`.
**Events:** `leave.requested`, `leave.approved`, `leave.rejected`, `leave.cancelled`.
**Permissions:** `leave.self`, `leave.view`†, `leave.approve`†, `leave.manage`†,
`leave.settings`.
**Screens:** `/app/leave`.

## 5.5 Payroll

**Tables:** `payroll_settings`, `salary_structures` (by effective date), `payroll_loans`
(advances), `payroll_runs`, `payroll_items` (one-off additions/deductions), `payslips`.
**Rules:**
- A run is one month: `draft → review → finalized → paid`. Whoever prepared it can't
  finalize it (four eyes), and finalizing needs a recent sign-in.
- `calc.py` is pure pay maths (tested with Hypothesis): basic, house rent, medical,
  conveyance; monthly, hourly or daily pay; overtime from attendance; unpaid leave;
  festival bonuses; advance repayments; a shortfall carries over as an advance.
- Salary tax is an editable slab table, **off** until the owner checks it with an adviser.
- Payslips as PDF in English or Bangla (`pdf.py`, WeasyPrint, fonts in `fonts/`). Staff
  see their own; notices never include the run's totals.
- A transfer sheet (CSV) lists who to pay by cash, bank or mobile wallet.
**Routes:** `/v1/payroll/settings`, `salaries`, `loans`, `runs` (+ `recompute`, `submit`,
`reopen`, `finalize`, `paid`, `items`, `transfers.csv`), `payslips` (+ `pdf`).
**Events:** `payroll.submitted`, `payroll.finalized` (accounting posts wages from it).
**Permissions:** `payroll.self`, `payroll.view`†, `payroll.manage`, `payroll.run`,
`payroll.approve`.
**Screens:** `/app/payroll`.

## 5.6 Tasks and onboarding

**Tables:** `projects`, `tasks`, `task_checklist_items`, `task_comments`,
`onboarding_templates`, `onboarding_runs`.
**Rules:**
- Projects have members and a home department. Members work on their projects; managers
  (`tasks.manage`, scoped) run every project in their departments.
- Board columns `todo → doing → done`, ordered by a position; `move` re-orders.
- "My work" groups a person's open tasks: overdue, today, this week, later.
- Onboarding (`onboarding.py`): a template lists items for the joiner or their manager,
  due N days after the start date, optionally pointing at a document. Starting it (by
  hand or automatically on `member.joined`) creates ordinary tasks; acknowledging the
  document ticks its item (`document.acknowledged` subscriber).
**Routes:** `/v1/projects`, `/v1/tasks` (+ `checklist`, `comments`, `move`),
`/v1/tasks/my-work`, `/v1/onboarding/templates`, `/v1/onboarding/runs`.
**Events:** `task.assigned`, `task.completed`, `task.commented`, `project.members_added`.
**Permissions:** `tasks.self`, `tasks.manage`†.
**Screens:** `/app/tasks` (board, task panel via `?task=`), onboarding under the same page.

## 5.7 Announcements

**Tables:** `announcements`, `announcement_reads`.
**Rules:** audience is everyone, some branches, or some departments (and their subtrees);
managers post only inside their scope; pinned first; a post counts as read when shown;
receipts ("read by 12 of 30", and who hasn't) for the author and admins.
**Routes:** `/v1/announcements` (+ `unread`, `read`, `receipts`).
**Events:** `announcement.published`.
**Permissions:** `announcements.read`, `announcements.post`†.
**Screens:** `/app/announcements`, "Latest news" on Home.

## 5.8 Documents

**Tables:** `documents`, `document_versions` (the file bytes, up to 10 MB, in Postgres),
`document_acks`, `document_passages` (extracted text for search).
**Rules:** audience is everyone, some roles, or some departments; every version kept;
policies can require acknowledgement per version; files checked by content and always
downloaded as attachments; text extracted from PDF, Word, PowerPoint and text files
(hostile XML refused) and searched with Postgres full-text search under the same
visibility rules.
**Routes:** `/v1/documents` (+ `versions`, `file`, `acknowledge`, `acknowledgements`),
`/v1/documents/search`, `/v1/documents/to-acknowledge`.
**Events:** `document.published`, `document.acknowledged`.
**Permissions:** `documents.read`, `documents.manage`.
**Screens:** `/app/documents`, "To read" on Home.

## 5.9 Notifications

**Tables:** `notifications`.
**How it works:** `subscribers.py` listens to events in the same transaction and writes
notifications for the right people: requests go to whoever can decide them **for that
person's department**; decisions go back to the requester; nobody is told about their own
action (except where it matters, like low stock); payslip notices leave out the totals.
Kept six months. `digest.py` sends the daily unread summary (once, in each person's
language, after an hour's grace; can be turned off; staff without email never get one).
**Routes:** `/v1/notifications` (+ `unread`, `read`, `read-all`);
`/internal/notifications/digest`.
**Screens:** the bell in the header.

## 5.10 Approvals

No tables: one inbox over other modules' pending items (leave requests, time fixes), each
filtered by that module's own permission, department scope and module switch. Decisions
call back into the module (same rules, same notifications). Oldest first; nobody sees
their own requests there.
**Routes:** `/v1/approvals`, `/v1/approvals/count`, `/v1/approvals/{kind}/{id}/approve|reject`.
**Screens:** `/app/approvals`, "Waiting for you" on Home.

## 5.11 Reports and signals

**Tables:** `report_subscriptions`, `signal_dismissals`.
**Rules:** the overview for any period and department: headcount by department, joiners
and leavers, attendance rate (present ÷ expected, where expected skips days off,
holidays and approved leave), late arrivals, leave taken by type, open and overdue tasks.
Worked out on each request. Managers see their own departments. Report emails go weekly
or monthly, computed **as the subscriber** (`member_ctx`), so they only show what that
person could see. **Signals** (`signals.py`): attendance dropping in a department,
projects slipping or due soon, and (only if chosen) people with unusually many open tasks
(at least 8 and more than twice the team's median); dismissible.
**Routes:** `/v1/reports/overview`, `subscription`, `signals` (+ `dismiss`);
`/internal/reports/send`.
**Permissions:** `reports.view`†.
**Screens:** `/app/reports`.

## 5.12 Imports

The spreadsheet import (CSV): people (matched by code, then email), departments from
paths like `Design / Motion`, and leave days left (recorded as adjustments). English or
Bangla headers, day-first dates, Bangla digits. A preview lists every row's problems;
nothing is saved until the whole file is clean; respects the people limit.
**Files:** `parse.py` (reading and cleaning), `service.py` (plan and apply).
**Routes:** `/v1/people/import`, `/v1/people/import/template`.

## 5.13 Privacy

Data rights. `GET /v1/privacy/workspace-export` (owner: a ZIP of every table, as JSON,
plus files), `POST /v1/privacy/workspace-import` (restore an export into a **new, empty**
workspace; `importer.py` remaps ids), `GET /v1/privacy/my-data` (anyone: what this
workspace holds about them, including their AI conversations). Deletion and restore live
in `routes_workspace.py`; the purge runs in `app/jobs/maintenance.py`.

## 5.14 Sales and tills

**Tables:** `shop_settings`, `tax_rates`, `product_categories`, `products`,
`cash_sessions` (drawers), `sales`, `sale_lines`, `tills`, `cashier_pins`.
**Rules:**
- **Taxes are the workspace's own** (`tax.py`): any number of named rates with return
  codes, inclusive or exclusive prices, compound taxes applied in order, defaults for new
  items, cash rounding. Nothing country-specific is built in.
- The till: open a drawer with a float, sell (cash, or credit to a customer), print an
  80 mm receipt from the browser, close by counting cash (expected = float + cash sales −
  refunds − cash expenses from the drawer).
- **Offline sales** are kept in the browser and sent later; each carries a `client_id`
  and the server keeps it once.
- Returns (cash or to the customer's account) and voids (with a reason) never delete
  anything; they add their own records.
- **Tills** (`tills.py`): a registered device gets a till token
  (`till_<tenant>_<secret>`); cashiers unlock it with a PIN (lock for 15 minutes after 5
  wrong tries) into a 12-hour, selling-only `pin` session; revoking the till ends its
  sessions.
**Routes:** `/v1/sales` (+ `receipt`, `returns`, `void`), `products`, `categories`,
`tax-rates`, `settings`, `drawer` (+ `open`, `close`), `drawers`, `summary`, `tills`,
`my-pin`; `/v1/till`, `/v1/till/unlock`.
**Events:** `sale.completed`, `sale.returned`, `sale.voided`, `sales.drawer_closed`.
**Permissions:** `sales.sell`, `sales.view`, `sales.manage`.
**Screens:** `/app/pos` (the till), `/app/sales` (history, summary, products, taxes,
tills), `/till` (the PIN pad on a shared device).

## 5.15 Customers and dues

**Tables:** `customers`, `customer_entries` (a ledger per customer: sales on credit,
payments, adjustments, returns).
**Rules:** balances come from the entries; credit limits are checked at the till;
adjustments need a note; statements print; reminders open WhatsApp with a ready message
(`web/src/lib/whatsapp.ts`).
**Routes:** `/v1/customers` (+ `payments`, `adjustments`, `statement`).
**Events:** `customer.paid`, `customer.adjusted`.
**Permissions:** `customers.view`, `customers.manage`.
**Screens:** `/app/customers`.

## 5.16 Expenses

**Tables:** `expense_categories` (seeded, editable), `expenses`.
**Rules:** paid from cash, bank, petty cash or the open drawer (counted at closing);
receipt photos (checked by content); petty cash top-ups; people with only
`expenses.record` see their own.
**Routes:** `/v1/expenses` (+ `receipt`), `categories`, `top-ups`.
**Events:** `expense.recorded`, `expense.changed`, `expense.deleted`, `expense.petty_top_up`.
**Permissions:** `expenses.record`, `expenses.manage`.
**Screens:** `/app/expenses`.

## 5.17 Inventory

**Tables:** `stock_items` (settings per product), `stock_levels` (per branch),
`stock_movements` (the ledger), `suppliers`, `supplier_entries`, `purchases`,
`stock_transfers`, `stock_counts`.
**Rules:**
- An item is tracked once it has opening stock, a purchase, or its settings say so.
- Levels per branch come from the movement ledger; one **weighted average cost** per item
  (`costing.py`).
- Sales, returns and voids move stock **in the same transaction** as the sale
  (in-transaction subscribers), so stock and sales never disagree.
- Selling before a delivery is recorded can push stock negative. When the delivery
  arrives, the units sold early are re-costed at the delivery's cost and a separate
  `revalue` movement ("cost correction") is posted, so the books still balance.
- Purchases record reclaimable input tax and what's owed to the supplier; supplier
  payments reduce it.
- Falling to the reorder level notifies the people who manage stock (`stock.low`).
**Routes:** `/v1/inventory/stock`, `items/{id}` (+ `movements`), `opening`, `purchases`,
`suppliers` (+ `payments`), `transfers`, `counts`, `adjustments`.
**Events:** `stock.moved`, `stock.low`, `purchase.received`, `supplier.paid`.
**Permissions:** `inventory.view`, `inventory.manage`.
**Screens:** `/app/inventory`.

## 5.18 Accounting

**Tables:** `accounts` (the chart), `accounting_settings` (lock date, account roles),
`journal_entries`, `journal_lines`, `tax_return_templates`.
**Rules:**
- A plain starting chart (`chart.py`), renamable; **roles** tell automatic postings which
  account to use (cash, sales, tax payable, inventory, cost of goods…).
- `postings.py` is pure: it turns a business fact into balanced legs (`sale()`,
  `stock()`, `purchase()`, `expense()`, `payroll()`…), and `balanced()` checks them.
- `service.py` subscribes **after commit** (`later=True`) to sales, returns, voids, stock
  movements, purchases, supplier and customer payments, dues adjustments, expenses and
  payroll, and posts each **once** (keyed by its source).
- Switching accounting on later **backfills** everything (`POST /v1/accounting/backfill`).
- Hand entries, reversals, a lock date (nothing posts before it).
- Reports: trial balance, profit and loss, balance sheet, ledgers, cash book.
- **Tax returns** are templates the workspace's accountant builds: boxes that add tax
  charged or the sales it was charged on (per rate), account movements, or other boxes;
  filled for any period.
- Property tests (`tests/test_ledger.py`) run thousands of random operations and check the
  books always balance and stock always reconciles.
**Routes:** `/v1/accounting/accounts`, `entries` (+ `reverse`), `ledger/{id}`,
`trial-balance`, `profit-and-loss`, `balance-sheet`, `cash-book`, `settings`,
`tax-returns` (+ `fill`), `backfill`.
**Permissions:** `accounting.view`, `accounting.manage`.
**Screens:** `/app/accounting` ("Books").

## 5.19 Automations

**Tables:** `automations`, `automation_runs`.
**Rules:** a trigger (a schedule in the workspace's time zone: every day, working day,
week or month; or an event: joining, leave, tasks, documents, news, payroll), conditions
on the event's values, and steps (notify people, create tasks). Recipients by role,
department, chosen people, the person it's about, people with overdue tasks or not
clocked in. They run **as their owner** (with that person's permissions), pause
themselves when they run too often or their owner leaves, never start each other
(`origin`), and keep a run history. Starter templates in the editor; the AI can draft
one from plain words for review.
**Files:** `engine.py` (schedules, matching, recipients, steps, `tick()`), `service.py`.
**Routes:** `/v1/automations` (+ `run`, `runs`), `/v1/automations/events`;
`/internal/automations/tick`.
**Events:** `automation.message`.
**Permissions:** `automations.manage`.
**Screens:** `/app/automations`.

## 5.20 Welcome

The first-day experience: an owner's checklist (`/v1/welcome/checklist`) and sample data
(`/v1/welcome/sample-data`: add, list, remove; every sample row is recorded in
`sample_records` so removing takes exactly those, and keeps any row something real now
points at). Join links and QR codes are in `platform/routes_join.py`.
**Screens:** the checklist card on Home (`components/welcome.tsx`).

## 5.21 The AI assistant

Not a module (it's `app/ai/`, above all modules), but it has its own tables in
`platform/ai_models.py`: settings, usage, conversations, messages, proposed actions.

| Feature (admins tick) | What it does | Route |
|---|---|---|
| Questions | "Ask my company" with cited sources | `POST /v1/ai/ask` |
| Documents | answers from policies and summaries | `POST /v1/ai/documents/{id}/summary` |
| Weekly brief | last week's report and pending approvals in a few lines | `POST /v1/ai/brief` |
| Actions | proposes tasks, comments, leave, announcements; the asker confirms | `/v1/ai/actions/{id}/confirm|cancel` |
| Writing | draft, improve, shorten, translate | `POST /v1/ai/write` |
| Automations | drafts an automation from plain words | `POST /v1/ai/automations/draft` |
| Signals | early warnings on Reports | (reports) |

Settings: `PUT /v1/ai/settings` (owner accepts terms; admins choose features),
`PUT/DELETE /v1/ai/own-key`, `GET /v1/ai/status`. Operators:
`/v1/operator/ai-allowances`, `/v1/operator/usage`.
**Screens:** `/app/ask`, the AI buttons in dialogs, Settings → AI assistant, Settings →
Platform (operators).
