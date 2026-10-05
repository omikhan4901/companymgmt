# 1. The product

## 1.1 In one paragraph

CompanyMgmt is a multi-tenant SaaS for running a small or medium business from one place:
the people (profiles, attendance, leave, payroll), the work (tasks, announcements,
documents), the shop (a till, customers' dues, expenses, stock) and the books
(double-entry accounting), with an optional AI assistant on top and an API for other
systems. It's built first for Bangladesh (English and বাংলা everywhere, Bangladesh Labour Act
defaults for leave, bKash-style wallets in payroll) but nothing is hard-wired to one
country: currency, time zone, work week, taxes and holidays are each workspace's own.

Many companies share one deployment. Each company is a **workspace** (in the code, a
**tenant**), and the database itself refuses to show one workspace's rows to another
(chapter 3.4).

## 1.2 Who it's for

| Business | What they switch on (at sign-up, by business type) | Interface mode |
|---|---|---|
| Shop (tea stall, pharmacy, phone shop) | attendance, sales & POS, customers & dues, expenses | simple |
| Restaurant | attendance, sales, inventory, expenses | simple |
| Retail with stock | attendance, sales, customers, inventory, expenses | standard |
| Office or agency | attendance, leave, payroll, expenses, tasks, announcements, documents | standard |
| Factory | attendance, leave, payroll, inventory, expenses, accounting | advanced |
| Other | attendance | standard |

The presets live in `api/app/modules/platform/catalog.py` (`BUSINESS_TYPES`). Anyone can
switch modules on or off later under **Settings → Modules**, within the plan's limit. The
interface mode is stored per workspace (Settings → Workspace); today it's a preference the
screens can read, not a different app.

## 1.3 The modules

"People" is always on. Every other module can be switched on or off.

| Module | Key | What people do with it |
|---|---|---|
| People | `people` | Profiles, departments as a tree, branches, managers who see only their own part of the tree |
| Attendance | `attendance` | Clock in and out from a phone, checked against the branch's location; time fixes with approval; monthly timesheets; CSV export |
| Leave | `leave` | Leave types, balances (accrual, carry-over, joining-date share), requests and approvals, holidays, team calendar |
| Payroll | `payroll` | Salaries, monthly pay runs (draft → submitted → finalized → paid), overtime from attendance, advances, bonuses, payslip PDFs in both languages, transfer sheets |
| Tasks & projects | `tasks` | Project boards, tasks with checklists and comments, "My work", onboarding checklists for new joiners |
| Announcements | `announcements` | News to everyone, some branches or departments, pinned posts, read receipts |
| Documents & policies | `documents` | Handbook and policies with versions, audiences, acknowledgements, full-text search |
| Sales & POS | `sales` | A till (also offline), receipts, returns, voids, cash drawers, configurable taxes, tills with cashier PINs |
| Customers & dues | `customers` | Customer accounts ("baki khata"), credit limits, payments, statements, WhatsApp reminders |
| Expenses | `expenses` | Expenses with receipt photos, categories, petty cash, cash taken from the drawer |
| Inventory | `inventory` | Stock per branch, purchases, suppliers and what's owed to them, transfers, counts, weighted average cost, low-stock alerts |
| Accounting | `accounting` | Double-entry books that post themselves from everything above; trial balance, P&L, balance sheet, ledgers, cash book, tax-return templates |

Always there, not switchable: the **approvals inbox** (leave and time fixes in one place),
**notifications** (the bell and a daily email), **reports** (attendance rate, lateness,
leave, overdue tasks, plus early-warning signals), **automations** (rules that notify
people or create tasks on a schedule or when something happens), **the AI assistant**
(off until a workspace turns it on), **data rights** (export, import, delete, restore),
**help and support**, and the **developer platform** (API keys, webhooks, company sign-in,
SCIM) on the plans that include it.

Dependencies between modules (`requires` in `catalog.MODULES`): payroll needs attendance;
inventory needs sales; most need people.

## 1.4 Plans

Defined as rows in the `plans` table (seeded by migrations `0001` and later); the public
site reads a copy in `web/src/data/plans.json`.

| Plan | Price (USD) | People | Branches | Modules | Custom roles | API & webhooks | Company sign-in & SCIM | AI questions / month |
|---|---|---|---|---|---|---|---|---|
| Free | 0 | 5 | 1 | 2 | – | – | – | 0 |
| Starter | 9 / month (90 / year) | 15 | 1 | 4 | – | – | – | 100 |
| Growth | 29 / month (290 / year) | 50 | 3 | all | ✓ | – | – | 500 |
| Business | 79 / month (790 / year), 150 people included, then 1.50 each | unlimited | unlimited | all | ✓ | ✓ | – | 2,000 |
| Enterprise | by agreement | unlimited | unlimited | all | ✓ | ✓ | ✓ | unlimited |

- Every new workspace gets a **14-day Growth trial**; afterwards it drops to Free, and
  nothing is deleted. Over the limits, extra modules turn **read-only**, never hidden.
- **Billing isn't built** (milestone M5, Paddle, is on hold by your decision). Until it is,
  you change a workspace's plan by hand in the database (chapter 11.6).
- AI allowances are a **platform setting**, not code: platform operators (emails in
  `PLATFORM_OPERATORS`) change them under Settings → Platform, and every affected
  workspace's owners and admins are notified.

## 1.5 Roles and permissions

Built-in roles (`catalog.BUILTIN_ROLES`):

| Role | In short |
|---|---|
| Owner | Everything, including billing and deleting the workspace |
| Admin | Everything except owner-only permissions (billing, deletion) |
| Manager | Runs a team: sees and approves for their department and the ones under it |
| Accountant | Prepares payroll, keeps the books, reads people, attendance and leave |
| Cashier | Sells, sees customers, records expenses, clocks in. Nothing about other people |
| Employee | Clocks in, asks for leave, sees their own payslips, tasks, news and documents |

Growth and above can make **custom roles** from any permissions (you can never grant a
permission you don't hold yourself). A permission can be **scoped**: a manager with
`leave.approve` and a department set on their membership only approves for that
department and everything below it. The full permission list is in chapter 13.3.

## 1.6 Languages and places

- Every screen, email and PDF exists in English and Bangla. People choose their own
  language; Bangla shows Bangla digits.
- Each workspace sets its country, currency, time zone, week start, days off and fiscal
  year; each branch has its own time zone and a location area for clock-ins.
- Dates are shown day-first; money uses the workspace currency.

## 1.7 What exists outside the app

- **The public site** (`/`, `/pricing`, `/developers`, `/security`, `/terms`, `/privacy`,
  `/dpa`, `/subprocessors`) in the same Next.js project as the app.
- **Help centre** at `/app/help`, and "Contact support" in the account menu.
- **SDKs** for TypeScript and Python in `sdk/` (not yet published to npm or PyPI).

## 1.8 What isn't built (on purpose, for now)

- **Billing** (M5, on hold): no checkout, invoices or dunning. Plans exist and are enforced.
- **Card or mobile-wallet payments at the till**: cash and customer credit only.
- **Receipt printers over Bluetooth/USB**: the browser prints 80 mm receipts.
- **SAML** (OpenID Connect is built; most identity providers speak both).
- **Workspace addresses on a wildcard domain** (`<slug>.companymgmt.app`): the code
  reserves and checks the names; DNS waits for your domain.
- **A dedicated database per enterprise customer**, table partitioning, read replicas:
  only worth it with real load.
- **Semantic (embedding) search** for documents: full-text search is used; the AI port
  already has `embed()`.

The full list of what's blocked on you is in `docs/PROGRESS.md` → "Blocked on the owner".
