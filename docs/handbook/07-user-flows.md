# 7. User flows

Each flow: who, the screens, the API calls, and what happens underneath. Use them to
find your way into the code: the screen is under `web/src/app/(product)/…`, the route in
`api/app/modules/<module>/routes.py`, the rules in that module's `service.py`.

## 7.1 An owner signs up

1. `/signup`: name, email, password, business name, country, business type, language.
   → `POST /v1/auth/signup` (rate-limited per IP; Turnstile after repeated failures).
2. The API, in one transaction: user (Argon2id hash, breached-password check), workspace
   with a slug, a 14-day Growth trial, built-in roles, the owner's membership and People
   profile, the business type's modules and their seed data (leave types, holidays, tax
   presets, expense categories, the chart of accounts…), an audit entry, and a
   verification email (outbox).
3. The browser gets an access token and the refresh cookie and lands on `/app`.
4. Home shows the **first-day checklist** (`/v1/welcome/checklist`): add a branch, invite
   people, try sample data (`POST /v1/welcome/sample-data`), and so on.
5. The email link opens `/verify-email` → `POST /v1/auth/email/verify`.

## 7.2 Bringing people in

Four ways, all under **Team** (`/app/team`):

| Way | Screen | Call | Then |
|---|---|---|---|
| Invite by email | Team → Invite | `POST /v1/invites` | email with a link → `/invite` → `POST /v1/invites/accept` |
| Join link / QR / WhatsApp | Team → Join link | `POST /v1/join-links` | person opens the link at `/join` → `POST /v1/join` |
| Staff account (no email) | Team → Add staff | `POST /v1/members/staff` | they sign in with workspace code + username, set their own password |
| Spreadsheet | People → Import | `POST /v1/people/import` (preview), then `?commit=true` | preview with row-by-row problems, then all-or-nothing |
| Company directory | Settings → Security | SCIM `POST /v1/scim/v2/Users` from Okta/Entra | provisioned and de-provisioned automatically |

Joining emits `member.joined`: onboarding checklists marked "start automatically" begin,
automations on joining run, and the `employee.onboarded` webhook goes out.

## 7.3 Signing in

- **Password** (`/login`): `POST /v1/auth/login`. With two-step on, the answer is a
  challenge → `POST /v1/auth/mfa/verify` with a TOTP or recovery code.
- **Staff**: workspace code + username + password, same endpoint.
- **Passkey**: `POST /v1/auth/passkeys/login/options` → browser WebAuthn →
  `POST /v1/auth/passkeys/login`.
- **Company account** (SSO): `POST /v1/sso/start` → provider → `/sso/callback` →
  `POST /v1/sso/callback`.
- A sign-in from a new device emails the person.
- Several workspaces: the account menu switches (`POST /v1/auth/switch`).
- Every 10 minutes the client silently refreshes (`POST /v1/auth/refresh`, rotating the
  cookie).

## 7.4 A staff member's day (attendance)

1. Home → **Clock in**. The browser asks for the location →
   `POST /v1/attendance/clock-in {lat, lng, accuracy}`.
2. The API finds the branch, measures the distance (`attendance/geo.py`), and by the
   workspace's mode records, flags, or refuses ("You're about 1.2 km from Gulshan kiosk").
3. Evening → **Clock out** (never refused). Forgot? Attendance → **Ask for a fix** →
   `POST /v1/attendance/corrections` → the manager is notified → approves in **Approvals**.
4. Month end: the manager opens **Attendance → Timesheet**, exports CSV.

## 7.5 Leave

1. Staff: Leave → **Ask for leave**, picks a type and dates; `GET /v1/leave/quote` shows
   the working days and what's left. → `POST /v1/leave/requests`.
2. `leave.requested` → bell notification for whoever has `leave.approve` over that
   person's department.
3. Manager: **Approvals** → Approve (`POST /v1/approvals/leave/{id}/approve`), balance
   re-checked. → `leave.approved` → the requester is told; the calendar shows them away;
   payroll counts unpaid leave; webhook `leave.approved`.

## 7.6 Payroll

1. Accountant: Payroll → Salaries (once per person, by effective date), advances.
2. **New run** for a month → `POST /v1/payroll/runs` (draft, computed from salaries,
   attendance overtime, unpaid leave, bonuses, advances). Add one-off items; recompute.
3. **Submit** → `payroll.submitted` → the approvers are told.
4. Someone else with `payroll.approve` **finalizes** (recent sign-in needed) →
   payslips are issued, `payroll.finalized` → staff are notified (no totals), the books
   post wages.
5. Download the **transfer sheet**, pay people, **mark paid**.
6. Staff: Payroll → their payslip → PDF in their language.

## 7.7 A shop day (POS, dues, expenses, stock, books)

1. Cashier opens `/app/pos` (or unlocks a shared till at `/till` with their PIN).
   **Open drawer** with the float → `POST /v1/sales/drawer/open`.
2. Tap items or type them in; take cash, show change; or put it on a customer's account
   (credit limit checked) → `POST /v1/sales` with a `client_id`. Offline? It queues and
   sends later.
3. In the same transaction: stock moves for tracked items (`sale.completed` in-transaction
   subscriber); falling to the reorder level notifies the stock managers.
4. Just before the response: the outbox delivers `sale.completed` → the books post the sale
   (cash/receivable, sales, tax payable; cost of goods and inventory), and webhooks are
   queued.
5. A customer pays their dues: Customers → the customer → **Record payment**. Reminders:
   **Share on WhatsApp**.
6. Paying the electricity bill from the drawer: Expenses → **Add**, paid from the drawer,
   photo of the receipt.
7. Evening: **Close drawer**, count the cash; the difference is recorded
   (`sales.drawer_closed`).
8. The owner: Sales → Summary (by day, tax by rate, best sellers, by seller); Books →
   profit and loss, balance sheet, cash book.
9. A delivery arrives: Inventory → **Receive purchase** (with what's still owed);
   later **Pay supplier**.

## 7.8 Work: tasks, news, documents, onboarding

- Manager: Tasks → **New project** (members, department) → tasks on the board; drag between
  columns. Assignees get `task.assigned`; comments and completion notify the people
  involved. Everyone sees their **My work** on Home.
- Announcements → **Post** to everyone / branches / departments; receipts show who read it.
- Documents → **Upload** a policy, choose the audience, tick "ask people to acknowledge";
  staff see "To read" on Home; acknowledgements counted per version.
- Settings → Onboarding: a checklist template; when someone joins, their items appear as
  tasks; reading the policy ticks its item.

## 7.9 Reports, automations and signals

- Reports → choose a period and department → `GET /v1/reports/overview`. **Email me this**
  weekly or monthly → `PUT /v1/reports/subscription`.
- Automations → **New** (or a template, or "describe it" with AI) → trigger, conditions,
  steps → saved; `/internal/automations/tick` or the event runs it as its owner.
- Reports → Signals: warnings, dismissible.

## 7.10 The AI assistant

1. The server has a Gemini key (or `AI_PROVIDER=fake` locally).
2. Owner: Settings → AI assistant → accepts the terms; admins tick features.
3. Anyone with `ai.use`: **Ask** (`/app/ask`) "Who is on leave next week?" →
   `POST /v1/ai/ask` → the model calls `leave.calendar` as the asker → an answer with
   numbered sources that open the right page.
4. With **actions** on: "Create a task for Rina to restock tea, due Friday" → the answer
   shows a proposed change with **Confirm** → `POST /v1/ai/actions/{id}/confirm` runs it as
   the asker, audited "via the assistant".

## 7.11 An enterprise customer connects its systems

1. Owner on Business: Settings → Developers → **New API key** with chosen permissions
   (shown once). Their developer reads `/developers` and `docs/api/README.md`.
2. **Webhooks**: add an HTTPS endpoint, pick events, copy the signing secret; deliveries are
   signed (`CompanyMgmt-Signature` header), retried, logged, resendable.
3. Enterprise: Settings → Security → **Company sign-in** (issuer, client id/secret) and
   optionally "require it"; **SCIM** token for provisioning; **network allowlist**.
4. A **sandbox** workspace (`POST /v1/workspace/sandbox`) to try things safely.

## 7.12 Data rights and leaving

- Anyone: Account → **Download my data** (`GET /v1/privacy/my-data`).
- Owner: Settings → Data → **Export everything** (ZIP); **Restore** an export into a new
  workspace.
- Owner: Settings → Data → **Delete workspace** (step-up) → everyone loses access → the
  owner can **Restore** for 30 days → then the nightly job erases it and emails a signed
  deletion certificate.

## 7.13 Getting help

Account menu → **Help** (`/app/help`, searchable articles in both languages) or
**Contact support** → `POST /v1/support` → an email to `SUPPORT_EMAIL` with the page and
workspace, reply-to the person.
