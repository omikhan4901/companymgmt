# CompanyMgmt — the next implementation plan

Written 5 October 2026 for the owner to read, change and approve before work restarts on
Thursday. It replaces "build more milestones" with two phases of depth:

- **Phase 1 — Every screen, done properly.** Take each tab on its own, work out how real
  businesses actually use it, find the intricate edge cases, test them, and build what's
  missing — including the obvious links to neighbouring screens (the till's cash spent should
  appear in Expenses; a purchase paid in cash should come out of the drawer; and so on).
- **Phase 2 — One business, from tea stall to enterprise.** Stop thinking in tabs. Follow a
  single business as it grows, and make the products work *together* at every stage:
  data flows between modules, a growth path between sizes and plans, one place to set the
  business up, and a permission system an owner can shape person by person.

Two more phases are proposed at the end (go-live and money; scale and reach), plus a short
Phase 0 to prepare the ground.

Nothing in this document is built yet. Where it says **"today"**, that's what the code does
now, checked on 5 October; items marked **(verify)** are suspected and get confirmed in the
Phase 0 audit before anything is built on them.

---

## Contents

0. [Why this plan, and what went wrong](#0-why-this-plan-and-what-went-wrong)
1. [How we'll work](#1-how-well-work)
2. [Phase 0 — Groundwork (2–3 days)](#2-phase-0--groundwork)
3. [Phase 1 — Every screen, done properly](#3-phase-1--every-screen-done-properly)
4. [Phase 2 — One business, from tea stall to enterprise](#4-phase-2--one-business-from-tea-stall-to-enterprise)
5. [Phase 2 track — Access you can shape person by person](#5-phase-2-track--access-you-can-shape-person-by-person)
6. [Proposed Phase 3 — Go live and get paid](#6-proposed-phase-3--go-live-and-get-paid)
7. [Proposed Phase 4 — Scale and reach](#7-proposed-phase-4--scale-and-reach)
8. [Order, effort and checkpoints](#8-order-effort-and-checkpoints)
9. [Decisions the owner needs to make](#9-decisions-the-owner-needs-to-make)
10. [Appendix A — Known gaps found so far](#appendix-a--known-gaps-found-so-far)
11. [Appendix B — Personas used throughout](#appendix-b--personas-used-throughout)

---

## 0. Why this plan, and what went wrong

The first build (M1–M11) was planned **feature by feature**: does the till sell, do the
books balance, does leave respect the balance. Every one of those is tested and works. What
was never planned is **how a real business lives in the product**:

- **Modules were built as islands joined by events, not as one business.** Money taken out of
  the till for milk is recorded in Expenses with "paid from: drawer", and the drawer only
  learns about it by matching the cashier and the time window. The till itself has no
  "pay out" button, and Expenses doesn't show which till or shift the cash came from.
- **Configuration was hard-coded for the first ten minutes, then forgotten.** The business
  type chosen at sign-up switches some modules on and is never used or changeable again. The
  "interface mode" (simple/standard/advanced) is saved and does nothing. Sample items (tea,
  coffee, samosa) look like built-ins. The till only links to "add items" when there are none.
- **There's no path to grow.** Plans are enforced but can't be changed from the app. Nothing
  helps a tea stall that opens a second branch, hires an accountant, or becomes an office.
- **Access control is role-shaped, not person-shaped.** One role per member, plus one
  department scope. No branch scope, no "only their own records", no per-person extra or
  removed permission, no money limits, no hiding salaries from a manager who can see people.
- **Tests proved rules, not journeys.** 321 tests check that each rule is correct; none check
  that a new owner can find where to add their own menu.

The fix is not more features. It's depth: understand each screen's real use (Phase 1), then
how they fit together for one business over time (Phase 2).

---

## 1. How we'll work

### 1.1 The loop for every screen and every journey

1. **Read** the screen and its API as they are today; list what it does and doesn't do.
2. **Scenarios first.** Write how 3 personas (Appendix B) actually use it, in their own words
   and in Bangladesh's reality: cash, credit to regulars, bKash, power cuts, shared phones,
   Bangla, Friday weekends, Ramadan hours, festival bonuses.
3. **Edge cases.** Enumerate them deliberately along ten axes (1.2).
4. **Classify** each finding: *bug*, *missing link* (to another screen), *missing feature*,
   *confusing UX*, *wrong default*, *needs a decision*. Record it in the **gap register**
   (`docs/gaps.md`, created in Phase 0).
5. **Owner review** of the scenario list and the decisions for that screen (short, async).
6. **Tests first** for every accepted item: API tests for rules, a browser scenario for the
   journey, both languages, phone and desktop.
7. **Build** the smallest change that makes the scenarios work.
8. **Walk it** in the browser as each persona, in Bangla and English, on a phone.
9. **Document**: handbook chapter 5 (module), chapter 7 (flows), the in-app help article.
10. **Done** when the exit criteria (1.3) hold.

### 1.2 The ten edge-case axes

Every screen gets examined along all ten. They're how "incredibly intricate" becomes
systematic instead of hopeful.

| Axis | Examples of what to try |
|---|---|
| **Time** | midnight in Dhaka vs UTC; month and year end; leap day; a shift crossing midnight; a sale at 23:59 with the drawer closed at 00:05; backdated entries; a locked accounting period; Friday weekends; Ramadan hours; daylight saving for branches abroad |
| **Money** | rounding to the poisha and to the nearest taka; inclusive vs exclusive tax; compound tax; discounts on top of tax; refunds of discounted items; very large amounts; zero and negative; change given; partial payments; overpayment |
| **Quantity** | fractions (0.5 kg, 250 ml); units vs packs (a carton of 12); negative stock; selling what was never received; returns of more than sold; wastage; staff meals |
| **People** | someone who left; someone on leave; someone in two branches; a manager who is also staff; the owner as a cashier; staff without email; two people with the same name; Bangla-only names |
| **Permissions** | each role; a scoped manager looking outside their scope; an API key; a till PIN session; a member removed mid-session; the last owner; a custom role with odd combinations |
| **Concurrency** | two cashiers on one drawer; two tabs editing the same thing; double-clicks; the same offline sale sent twice; a payroll run recomputed while someone edits a salary |
| **Connectivity** | offline at the till; a request that times out but succeeded; slow 3G; the app left open overnight; a refresh mid-form |
| **Volume** | 5 records vs 50,000; a 300-line purchase; a 2,000-person payroll; a year of daily sales on the reports page; long names; 50 branches |
| **Language and devices** | Bangla digits typed into amounts; mixed-script names; right-to-left text pasted in; a 360 px phone; a shared tablet; printing on 58 mm and 80 mm |
| **Lifecycle** | a module switched off and on again; the plan dropping to Free; a workspace restored from export; sample data removed after real data was added; a branch closed |

### 1.3 Exit criteria for a screen

- Every accepted scenario works end to end for every persona it applies to.
- Every edge case found has a test or a written reason why not.
- Every link to another screen that a real user would expect exists in both directions
  ("see the sale" from a customer's statement; "see the customer" from a sale).
- Nothing on the screen is hard-coded that a real business would want to change; everything
  configurable is findable from the screen itself (a "set up" link where it applies).
- Empty states teach: they say what this screen is for and what to do first.
- Help article updated; handbook chapters 5 and 7 updated.
- `E2E=1 scripts/check.sh` passes.

### 1.4 Testing additions

- **Scenario tests** (new): long, story-like API tests per persona ("a tea stall's Saturday")
  in `api/tests/scenarios/`, reusable fixtures for each persona's workspace.
- **Persona demo workspaces**: `scripts/seed_persona.py tea|retail|office|factory|group`
  to create a realistic workspace for walking through screens by hand.
- **Clock control** in tests (freeze "now" in a chosen time zone) so time edge cases are
  routine, not accidents like the books-test failure found on 5 October.
- **Visual walkthrough**: a Playwright script that screenshots every screen per persona in
  both languages and both sizes, for the owner to review in one place.

---

## 2. Phase 0 — Groundwork

Two to three days before Phase 1 starts. Small, but makes everything after it faster.

| # | Task | Output |
|---|---|---|
| 0.1 | **Gap register**: `docs/gaps.md` with every known gap (Appendix A to start), each with screen, type, severity, persona affected, status | the single list Phase 1 and 2 burn down |
| 0.2 | **Configuration audit**: list every hard-coded default and preset in the code (business types, modules, roles, leave types, holidays, expense categories, chart of accounts, tax presets, sample data, report settings, notification rules), and for each: can an owner see it? change it? where? | a table in `docs/gaps.md`; feeds 4.4 |
| 0.3 | **Cross-module map as it is today**: every event and who listens, every place one module reads another, every screen link | a diagram in the handbook; shows the missing links |
| 0.4 | **Persona seeds** and scenario-test scaffolding (1.4) | `scripts/seed_persona.py`, `api/tests/scenarios/` |
| 0.5 | **Clock control** in tests | a fixture to freeze time in any zone |
| 0.6 | **Walkthrough screenshots** of every screen per persona | a folder the owner reviews before Phase 1 starts |
| 0.7 | Fix the **verify** items in Appendix A: confirm or strike each | updated Appendix A |

---

## 3. Phase 1 — Every screen, done properly

### 3.0 Order

Grouped into clusters, in the order a growing business meets them. Each cluster ends with a
checkpoint where the owner walks it.

| Cluster | Screens | Why this order |
|---|---|---|
| **1A The shop's money** | Till (POS), Sales, Expenses, Customers & dues, Inventory, Books | the tea stall's daily life, and the owner's own example; money must reconcile before anything else matters |
| **1B People and time** | People, Attendance, Leave, Payroll | every business with staff; payroll draws on all of them |
| **1C Work** | Tasks & projects, Announcements, Documents, Approvals | offices and agencies |
| **1D Seeing the business** | Home, Reports, Ask (AI), Automations, Notifications | only meaningful once the data above is right |
| **1E Running the workspace** | Team, Settings, Account, Sign-up & first day, Help, public site | the frame around everything |

Each screen below has: **purpose**, **today**, **real scenarios**, **links to build**,
**edge cases to test**, **likely build items**, **questions for the owner**. The lists are
starting points; step 2 of the loop (scenarios first) will grow them.

---

### 1A. The shop's money

#### 1A.1 Till (`/app/pos`, `/till`)

**Purpose.** Sell fast, take cash (or credit), hand over change, and account for every taka in
the drawer at the end of a shift.

**Today.** Drawer open/close with a float and counted cash; item buttons and typed items;
cash, change and credit to a customer; per-line discount; browser receipts; offline queue in
the browser; returns and voids from Sales; cashier PINs on registered tills. Single price per
item, no variants or modifiers, no non-cash payment methods, no pay-out from the till, no
shift handover, "add items" link only when the till has no items.

**Real scenarios.**
- Tea stall, 6 a.m.: owner opens with ৳500 float. Sells 140 cups by 11 a.m., mostly ৳10–15,
  many to regulars on credit ("write it down, I'll pay Friday"). Sends the helper to buy 5 L
  of milk with ৳400 from the drawer. A regular pays ৳300 of last week's dues in cash.
- Same stall: a customer pays with bKash (send money to the owner's number). The cash in the
  drawer is less than sales, correctly.
- Evening: the helper takes over the drawer (shift handover) — the morning count is closed,
  the evening one opens with whatever's left, without the owner present.
- Owner takes ৳2,000 home at night (not an expense: owner's drawing).
- A cup of tea for each staff member at lunch (stock used, not sold).
- Small/large tea at different prices; sugar-free; "extra ginger" (+৳5).
- Power cut, phone offline for 2 hours; 60 sales queued; one item's price changed meanwhile.
- Retail: barcode scanner (keyboard input), quantity by weight, price per branch, a
  promotion "buy 2 get 1", returns without a receipt.

**Links to build.**
- **Pay out** from the till → creates an Expense (category, payee, note, receipt photo)
  linked to the drawer session, visible on the drawer's close sheet and in Expenses with
  "from till: Gulshan, shift of Karim, 3 Oct".
- **Cash in** to the till (change bought from the bank, owner adds cash) and **owner
  drawing** (cash taken by the owner) → books post to capital/drawings, not expenses.
- **Receive payment** of dues at the till → Customers ledger + drawer cash in.
- **Pay a supplier** from the till → Inventory supplier balance + drawer.
- **Staff meal / wastage** button → stock out with a reason, no sale.
- **Edit items** link always visible to managers, not only when empty.

**Edge cases to test.**
- Sale at 23:58, drawer closed at 00:03 in Dhaka: which business day? Which drawer?
- Offline sale sent after the drawer was closed; after the item was deactivated; after its
  price changed; after the cashier was removed.
- Two cashiers selling into one drawer at once; one closes it while the other sells.
- Change owed bigger than cash in the drawer.
- Credit sale beyond the customer's limit; to a customer marked inactive; while the customer
  record is being edited elsewhere.
- Discount bigger than the line; discount on a tax-inclusive item and its tax.
- Rounding to ৳1 with a mixed basket; refund of a rounded sale.
- Quantity 0.25 of a per-kg item; 1,000 of an item.
- A till PIN session trying to open settings; PIN lockout during a rush.
- Receipt in Bangla with a 40-character item name on 58 mm paper.
- Pay-out larger than the cash in the drawer.

**Likely build items.** Payment methods (cash, bKash/Nagad/card as *recorded* methods, split
payment); pay-out / cash-in / drawing actions; shift handover; item variants and modifiers;
per-branch prices; barcode field and search; quick-keys layout per branch; stock-out reasons
(staff meal, wastage); "always show edit items" for managers.

**Questions for the owner.** Should bKash/Nagad be recorded methods only (no integration)
for now? Do variants come before per-branch prices? Is owner drawing visible to managers?

#### 1A.2 Sales (`/app/sales`)

**Purpose.** See what was sold, fix mistakes, manage items and taxes, understand the day.

**Today.** Tabs: sales, summary, products, taxes, drawers, tills. Returns, voids with reason,
receipts, period summary with tax by rate and best sellers, products and categories, tax
rates, drawer history, registered tills.

**Real scenarios.** Owner checks yesterday's takings per branch and per cashier; finds a sale
rung up twice and voids it; a customer returns a damaged item for credit to their account;
the accountant exports a month of sales for VAT; a manager reprices 40 items before Eid;
the owner compares this Friday with last Friday.

**Links to build.** Sale → customer statement and back; sale → stock movements and journal
entry ("how did this hit the books?"); drawer → its sales, pay-outs, expenses and count
differences; product → its stock, purchase history and margin; summary → books P&L for the
same period (and why they differ: credit sales, returns).

**Edge cases.** Void after the drawer is closed; return after the books period is locked;
return of a discounted line from a multi-line sale; return twice of the same line; item
deleted vs deactivated with past sales; tax rate changed after sales exist (past sales keep
the old rate); 50,000 sales in a month (paging, export); summary across a DST boundary for
a branch abroad; sales by a cashier who has left.

**Likely build items.** Bulk price edit and CSV import/export of items; per-branch and
per-cashier filters everywhere; drawer close sheet with every movement; margin per item
(when inventory is on); "explain this number" links into the books.

#### 1A.3 Expenses (`/app/expenses`)

**Purpose.** Record money going out that isn't stock: rent, electricity, transport, repairs,
wages paid daily in cash, tea for guests.

**Today.** Categories, amount, payee, note, paid from (petty cash, drawer, bank, other),
receipt photo, petty cash top-ups. Drawer link is only `paid_from = drawer` + who + time
window; no link to the drawer session, no supplier, no approval, no recurring expenses, no
employee claims.

**Real scenarios.**
- **The owner's own example:** expenses paid from the till must show up in Expenses with
  the till and shift they came from, and in the drawer's close sheet — one record, two views.
- Rent every month on the 1st (recurring); electricity bill varies monthly.
- A helper's daily wage paid in cash from the drawer — is it an expense or payroll?
- Staff buys office supplies with their own money and claims it back (employee expense
  claim → approval → reimbursed in cash or in the next payroll).
- Office manager has ৳5,000 petty cash; tops up when low; the accountant reconciles.
- Expenses by branch and by project (client work at an agency).
- Expense needs approval above ৳10,000.

**Links to build.** Expense ↔ drawer session (a real foreign key, not a time window);
expense ↔ supplier (a bill from a supplier); expense ↔ project/client (cost tracking);
claim → approvals inbox → payroll item or cash payout; expense ↔ journal entry; recurring
schedule → automation-like generator; branch on every expense.

**Edge cases.** Expense edited after its drawer closed (the count is already done);
expense deleted after the period is locked; receipt photo of 12 MB from a phone; a claim by
someone who left before reimbursement; currency of a foreign purchase; split an expense
across two categories; backdated rent for last month; negative expense (refund from a shop).

**Likely build items.** Drawer session link and "from the till" view; expense claims with
approval and reimbursement (payroll or cash); recurring expenses; approval thresholds;
project/cost-centre tags; supplier bills; filters by source (till, petty cash, bank, claims).

#### 1A.4 Customers & dues (`/app/customers`)

**Purpose.** Know who owes what ("baki khata"), collect it, and stay friendly.

**Today.** Customers with phone, address, credit limit; ledger of credit sales, payments,
adjustments; statements; WhatsApp reminders. No branch, no customer groups, no price lists,
no B2B invoices with due dates.

**Real scenarios.** Regulars who pay weekly; a customer who pays some of it; a customer who
moved away (write-off); a corporate client billed monthly with an invoice and 30-day terms;
the same customer buying at two branches; a reminder in Bangla with the exact amount; an
owner asking "who hasn't paid in 30 days?".

**Links to build.** Payment at the till and in Customers both land in the same ledger and the
drawer (if cash) or bank; statement lines link to the sales; write-off posts to bad debts;
ageing report (0–30, 31–60, 60+); dues on Home ("৳12,400 owed, 3 overdue").

**Edge cases.** Payment bigger than the balance (credit on account); payment against a
specific sale vs the oldest first; a return credited to a customer with no dues; a customer
merged with a duplicate; a phone number shared by two customers; deleting a customer with
history.

**Likely build items.** Ageing and overdue list; write-off; merge duplicates; invoices with
terms for B2B (could become its own module — see question); customer groups and price lists;
SMS reminder option.

**Question for the owner.** Should B2B invoicing (quotes → invoices → payments, with due
dates) be part of Customers, or a separate "Invoices" module for offices and agencies?

#### 1A.5 Inventory (`/app/inventory`)

**Purpose.** Know what's on the shelf, what it cost, what to reorder, where it went.

**Today.** Stock per branch from a movement ledger; weighted average cost; purchases with
input tax and supplier balance; supplier payments; transfers; counts; adjustments; low-stock
alerts; negative-stock re-costing. No units of measure conversion, no recipes, no purchase
orders, no expiry dates, no reorder suggestions.

**Real scenarios.**
- Tea stall buys milk, sugar, tea leaves daily at the market with drawer cash — is that a
  purchase or an expense? (A purchase if they want cost per cup; an expense if they don't.)
- A cup of tea uses 150 ml milk, 10 g sugar, 3 g leaves — **recipes** turn sales into
  ingredient use and real cost per cup.
- Buy sugar by the 50 kg sack, use it by the gram (**units of measure**).
- Pharmacy/grocery: expiry dates and batches; first-expiry-first-out.
- Retail: purchase orders to suppliers, partial deliveries, supplier returns.
- Month-end count finds shrinkage; owner wants to know where it went.

**Links to build.** Purchase paid in cash from the till → drawer and supplier ledger; purchase
on credit → supplier dues on Home; recipe-based stock use from every sale; wastage and staff
meals from the till; reorder suggestions → draft purchase order; stock value on the balance
sheet reconciled with the stock report.

**Edge cases.** Count during trading hours (sales between count and post); transfer in
transit when a branch closes; purchase with a line returned to the supplier; cost of a
product with zero stock; recipe change mid-day; unit conversion rounding; 300-line purchase
from a spreadsheet.

**Likely build items.** Units and pack sizes; recipes / bill of materials; purchase orders;
supplier returns; batches and expiry (optional per item); reorder suggestions; stock
valuation report matching the books.

#### 1A.6 Books (`/app/accounting`)

**Purpose.** Show the owner and the accountant the truth about money, without either of them
doing bookkeeping by hand.

**Today.** Self-posting double-entry from sales, returns, voids, stock, purchases, payments,
dues, expenses, payroll; hand entries; reversals; lock date; trial balance, P&L, balance
sheet, ledgers, cash book; tax-return templates.

**Real scenarios.** The owner asks "did I make money this month?" in plain words; the
accountant reconciles the bank statement; opening balances when a business moves in from
paper; owner's capital and drawings; loans; depreciation of a fridge; branch-wise P&L; a
second company in the same group.

**Links to build.** Every journal line links back to its source (sale, expense, payroll run);
bank reconciliation against imported statements; opening balances wizard; branch and
project as reporting dimensions on journal lines; drawings and capital from the till.

**Edge cases.** Backfill when switching accounting on with a year of history; lock date
moved backwards; reversing an entry that was already reversed; a sale voided after its
period was locked (post to the current period with a note); rounding differences; very old
data in a new chart.

**Likely build items.** Plain-language P&L ("you earned ৳…, spent ৳…, kept ৳…"); opening
balances; bank reconciliation; dimensions (branch, project); fixed assets and depreciation;
"where did this number come from" drill-down everywhere.

---

### 1B. People and time

#### 1B.1 People (`/app/people`)

**Purpose.** One true record of everyone who works here.

**Today.** Profiles (code, names, contact, department, branch, job title, employment type,
status, dates, encrypted national ID, notes); department tree; import from CSV. No
**reports-to** (line manager), no positions, no documents per person, no emergency contact,
no history of changes (promotion, transfer), single branch per person.

**Real scenarios.** A helper who works mornings at one stall and evenings at another; a
promotion with a salary change on a date; a transfer between branches; an employee's NID
and appointment letter stored privately; "who reports to Rina?"; an org chart for a
200-person factory; a seasonal worker for Eid; someone rehired after a year.

**Links to build.** Person → their attendance, leave, payslips, tasks, assets (Phase 4),
documents acknowledged, sales made, expenses claimed — one profile page with tabs.
Change of department/branch/salary → effective dates that payroll and reports respect.

**Edge cases.** Two people with the same name; a person without an account; deleting vs
leaving; rehire keeps history; department deleted with people in it; import that moves 50
people at once; Bangla-only names sorted correctly.

**Likely build items.** Reports-to and org chart; employment history with effective dates;
multiple branches per person; private documents per person; profile hub linking every module.

#### 1B.2 Attendance (`/app/attendance`)

**Purpose.** Know who is at work, when, and where, fairly and with as little effort as
possible from staff.

**Today.** Tabs: mine, today, records, corrections, timesheet. Clock in/out with a location
check per branch (off/record/require), positions rounded and saved only at clock events;
overnight shifts counted to the day they started; corrections with approval; monthly
timesheet and CSV export; one "working day starts at" time and grace per **workspace**. The
database already allows a `kiosk` source **(verify whether any screen uses it)**. No shifts,
rosters, breaks, or overtime approval.

**Real scenarios.**
- Factory: three shifts (6–2, 2–10, 10–6); a worker swaps a shift with a colleague; night
  shift crosses midnight and the weekly day off.
- Tea stall: helpers have no smartphones; they clock in on the owner's phone or a shared
  tablet at the counter with a PIN (**kiosk mode**, like the till).
- Agency: hybrid days ("working from home" allowed on Tuesdays), field visits to clients
  (record location, don't require it), a client site as a temporary "branch".
- Ramadan: shorter hours for a month; lateness rules follow.
- A worker forgets to clock out for three days; a manager fixes a week at once.
- Overtime: only counts when a manager approves it, and only beyond the rostered hours.
- Public holiday worked: double pay or a day in lieu (links to leave and payroll).

**Links to build.** Rosters → expected hours → lateness and absence in reports; approved
overtime → payroll items; holiday worked → compensatory leave; absence without leave →
payroll deduction (rule chosen by the owner); clock-in at a branch → that branch's till and
drawer ("open your drawer?" for cashiers).

**Edge cases.** Clock-in 2 minutes before a shift that starts at midnight; a roster changed
after people clocked in; GPS accuracy 300 m in a dense area; phone clock wrong by an hour
(server time wins); two clock-ins from two devices at once; a branch moved (new location
area) with historic records; a person transferred mid-month (which branch's rules?);
daylight saving for a branch abroad; a kiosk tablet offline for a shift.

**Likely build items.** Shifts and rosters; per-branch and per-shift lateness rules; kiosk
mode with PINs or QR; overtime approval; breaks; bulk corrections; Ramadan/seasonal
schedules; absence rules feeding payroll.

#### 1B.3 Leave (`/app/leave`)

**Purpose.** Ask for time off, see what's left, approve fairly, and plan cover.

**Today.** Tabs: mine, requests, calendar, balances, settings. Types, yearly or monthly
accrual, carry-over limit, half days (morning/afternoon), holidays, work week, joining-date
share, adjustments, approvals with no self-approval, a calendar that hides reasons,
Bangladesh defaults.

**Real scenarios.** Casual leave for a family wedding in Sylhet (3 days around a Friday);
sick leave with a doctor's note after 2 days; maternity leave of 16 weeks with its own rules
(paid, not counted against others); earned leave encashed at year end or on leaving; a
manager on leave whose approvals go to their deputy; two people from a 3-person team asking
for the same Eid days (cover warning); leave in hours for an office ("leaving at 3 pm");
a compensatory day for working on a holiday.

**Links to build.** Leave → roster gaps (attendance) and cover warnings; unpaid leave →
payroll (exists); encashment → payroll; maternity → payroll rules; leave approval →
delegation when the approver is away (approvals); leave balance on the person's profile.

**Edge cases.** Leave that spans a holiday added later; a request across the leave-year
boundary; half day on a half working day; a balance going negative after an adjustment;
a type deactivated with pending requests; a person who changes department mid-request
(who approves?); accrual for someone joining on the 31st; carry-over when the year's
settings change.

**Likely build items.** Attachments (doctor's notes); delegation; cover/clash warnings;
encashment; compensatory leave; hourly leave; per-type rules (documents required, notice
period, max consecutive days).

#### 1B.4 Payroll (`/app/payroll`)

**Purpose.** Pay everyone correctly, on time, and leave a record that holds up.

**Today.** Tabs: mine, runs, salaries, advances, settings. Salary structures by effective
date (monthly/hourly/daily; cash, bank, wallet); advances; runs draft → review → finalized →
paid with four eyes; overtime from attendance; unpaid leave; festival bonus as a share of
basic after a minimum service; one-off items; transfer sheet; payslip PDFs in both
languages; an editable tax table, off by default. No provident fund, gratuity, arrears,
final settlement, weekly or daily pay runs, or "paid from" account.

**Real scenarios.**
- Tea stall: helpers paid **daily or weekly in cash from the drawer**; an advance of ৳500
  repaid from the next three weeks.
- Grocery: monthly salaries, some by bKash, some in cash; two Eid bonuses a year.
- Factory: piece-rate workers (paid per unit produced); attendance bonus for no absences;
  provident fund (employee and employer shares); gratuity on leaving.
- Agency: a raise backdated two months (arrears); someone leaves on the 17th (final
  settlement: pro-rated salary, leave encashment, advances recovered, gratuity).
- Bank transfer file for the company's bank (BEFTN); bulk wallet sheet.

**Links to build.** Run paid → from which account (bank, drawer, petty cash, wallet) → books
and, for cash, the drawer; advances given from the drawer → payroll recovery; expense claims
→ reimbursement items; final settlement from People (leaving) → payroll; payslips →
person's profile and "my data".

**Edge cases.** A salary changed after the run was drafted; a person joining on the 31st;
leaving on the 1st; negative net pay (advance bigger than salary → carry); rounding to the
taka on payslips vs the books; two runs for one month (regular + bonus); reopening a
finalized run after payslips were seen; currency change; 2,000 people in one run.

**Likely build items.** Pay frequencies (daily/weekly/monthly) and pay groups; paid-from
account; piece rate; provident fund and gratuity; arrears; final settlement; bank and wallet
file formats; payslip delivery by WhatsApp/email.

---

### 1C. Work

#### 1C.1 Tasks & projects (`/app/tasks`)

**Today.** Projects with members and a home department; boards (to do, doing, done); tasks
with assignee, due date, priority, checklist, comments; My work grouped overdue/today/week/
later; onboarding checklists that become tasks. No recurring tasks, dependencies, time
logging, estimates, clients, budgets or guests.

**Scenarios.** "Clean the tea urn every evening" (recurring, assigned to whoever's on the
evening shift); an agency's client campaign with a budget, hours logged by designers, and
expenses for printing; a factory maintenance checklist every Monday; a task waiting on
another; a client who should see only their project's progress.

**Links to build.** Time logs → cost per project (salary per hour from payroll); project
expenses (1A.3); project revenue (invoices, 1A.4); task assignee on leave → warning;
automations that create recurring tasks; tasks from announcements ("everyone read and
confirm").

**Edge cases.** A recurring task when the assignee leaves; a project archived with open
tasks; moving a task between projects with different members; 2,000 tasks on one board;
due dates in a different branch's time zone; a checklist of 100 items.

**Likely build items.** Recurring tasks; time logging; dependencies; project budgets and
clients; guest access (with section 5); templates.

#### 1C.2 Announcements (`/app/announcements`)

**Today.** Posts to everyone, branches or departments; pinned; read receipts; managers post
within their scope; notifications. No scheduling, expiry, acknowledgement or attachments.

**Scenarios.** Eid holiday notice scheduled for 8 a.m.; an urgent safety notice everyone must
acknowledge; a notice for the night shift only; a post with a PDF roster attached; a notice
that disappears after the event.

**Build.** Scheduled publish; expiry; "must acknowledge"; attachments (via documents);
audience by shift/role; templates in both languages.

#### 1C.3 Documents (`/app/documents`)

**Today.** Documents with audiences (everyone, roles, departments), versions up to 10 MB,
acknowledgements per version, full-text search, AI summaries. No folders, templates,
review dates or per-person private documents.

**Scenarios.** Offer and appointment letters filled from a person's profile and salary;
an employee's NID scan and contract kept privately on their profile; policies reviewed every
year (reminder to the owner); a folder per department; a trade licence that expires (reminder
30 days before).

**Build.** Folders; templates with fields from People/Payroll; private per-person documents;
review and expiry dates with reminders (automations); certificates and licences register.

#### 1C.4 Approvals (`/app/approvals`)

**Today.** One inbox for leave and time fixes from a manager's own departments, oldest
first; approve or reject with a note.

**Scenarios.** An expense claim of ৳3,000 (manager) vs ৳30,000 (manager, then owner); a
purchase over ৳50,000 (owner); a refund over ৳2,000 at the till (head cashier); a payroll
run (owner); a new hire's salary (owner); a manager on leave (deputy approves); approving
from the notification on a phone without opening the app.

**Build.** A general approval engine: request types registered by modules, **chains** and
**thresholds** set in Business setup, delegation, reminders and escalation after N days,
approve from notification/email links, a history per request, and the limits from 5.1.

---

### 1D. Seeing the business

#### 1D.1 Home (`/app`)

**Today.** Cards: clock in/out, who's at work, hours, approvals waiting, first days, to read,
news, my work, who's away, the first-day checklist and a trial banner. **No shop cards**: a
tea stall owner sees nothing about takings, the drawer, dues or stock.

**Scenarios.** Rahim at 10 p.m.: today's takings, cash that should be in the drawer, dues
collected and still owed, items running out. Karim (cashier): "open your drawer", his sales
today. Nasrin: both branches side by side. Farhana (HR): who's in, who's late, requests
waiting, birthdays and work anniversaries. Mr. Chowdhury: a group dashboard.

**Build.** Cards per module and role, arranged by stage and permissions; owner can pin and
reorder; numbers link to their source; a branch switcher for multi-branch owners.

#### 1D.2 Reports (`/app/reports`)

**Today.** An HR-shaped overview (headcount, attendance rate, lateness, leave, overdue tasks)
with weekly/monthly emails and signals. Shop reports live in Sales and Books.

**Build.** One Reports area with sections: Sales (takings by day/branch/cashier/hour, best
sellers, margin), Money (P&L in plain words, cash flow, dues ageing, supplier dues), Stock
(value, slow movers, wastage), People (existing), Work (project time and profitability);
comparisons (this week vs last); export to Excel; every report schedulable by email.

#### 1D.3 Ask (AI), 1D.4 Automations, 1D.5 Notifications

- **Ask:** capabilities for every new screen (pay-outs, claims, recipes, ageing); re-run the
  parity test; 30 real questions per persona in both languages as a test set.
- **Automations:** new triggers (drawer difference over ৳X, pay-out over a limit, dues 30
  days overdue, stock expiring, claim waiting 3 days, licence expiring) and steps (send a
  WhatsApp/SMS later, create a purchase order draft).
- **Notifications:** per-person settings by kind and channel; quiet hours; digest frequency;
  owner defaults per business type.

---

### 1E. Running the workspace

#### 1E.1 Team (`/app/team`)

**Today.** Members, invites, staff accounts without email, join links with QR, roles
(built-in and custom), password resets for staff, removal. One role and one department
scope per member.

**Build.** The permission builder from section 5; bulk invite from the people list; templates
per business type; "copy access from"; "view as"; offboarding checklist (revoke access,
return assets, final settlement, archive).

#### 1E.2 Settings → Business setup

**Today.** Tabs: modules, branches, plan, AI, audit (plus developers, security, data and
platform where allowed). The plan tab shows the plan and limits but can't change them.

**Build.** Section 4.4. Every hard-coded default from the Phase 0 audit gets a home.

#### 1E.3 Account (`/app/account`)

**Check.** Language, theme, two-step, passkeys, devices, notifications, data download — each
scenario walked; add per-person notification channels and interface mode override.

#### 1E.4 Sign-up and the first day

**Today.** Sign-up asks for business type, which picks modules once. The first-day checklist
and sample data are generic.

**Scenarios.** Rahim signs up on his phone in Bangla in under two minutes and sells his first
cup within five; Nasrin imports her item list from Excel; Farhana imports 30 people.

**Build.** A first-day flow per business type (tea stall: add your menu → open your drawer →
sell; office: add people → set leave → invite); sample data marked "sample" everywhere with
"replace with my own"; import from Excel for items, customers, suppliers and opening stock,
not only people.

#### 1E.5 Help and the public site

Every screen links to its help article; articles cover the new scenarios; the public site's
claims are re-checked against what's built after each cluster.

---

## 4. Phase 2 — One business, from tea stall to enterprise

### 4.1 The aim

Follow one business through six stages. At each stage ask: what does the owner need, which
modules are involved, how does data flow between them, what must they configure, and what
happens at the **transition** to the next stage. The output is not features in isolation but
a product that grows with its customer.

### 4.2 The six stages

| Stage | Example | People | Branches | What changes |
|---|---|---|---|---|
| **S0 Solo stall** | Rahim's tea stall | owner + 2 helpers | 1 | cash, credit to regulars, daily bazar, daily wages from the till |
| **S1 Small shop** | a grocery with stock | 5–10 | 1 | stock, suppliers, monthly salaries, a cashier who isn't the owner |
| **S2 Two locations** | second outlet | 10–25 | 2–3 | branch managers, transfers, per-branch P&L, shared customers |
| **S3 Office / agency** | 30-person agency | 20–60 | 1–2 | leave, payroll, projects, documents, approvals, an accountant |
| **S4 Multi-branch company** | retailer or factory | 100–500 | 5–30 | regions, HR team, approval chains, rosters, budgets, audits |
| **S5 Enterprise / group** | group of companies | 500–5,000 | many | several legal entities, consolidated reports, SSO/SCIM, API, strict access, data export to their systems |

### 4.3 For each stage, the deliverables

1. **Journey script**: a day, a week and a month-end, written as steps with screens and data.
2. **Module map**: which modules are on, and the data that flows between them (4.5).
3. **Configuration**: what the owner sets up, in order, and where (4.4).
4. **Roles and access**: the people and what each may do (section 5).
5. **Transition to the next stage**: the trigger (hiring an accountant, opening a branch),
   what the product suggests, what changes automatically, what the owner chooses.
6. **Scenario test**: the journey as an automated API test + a browser walkthrough.
7. **Gaps** into the register, fixed in the stage's build list.

### 4.3a Stage by stage: first sketches

These are starting points for each stage's journey script (4.3 step 1); Phase 2 turns each
into a full script, a scenario test and a build list.

#### S0 — Rahim's tea stall (owner + 2 helpers, 1 stall)

- **A day.** 6:00 Rahim opens the drawer (৳500 float) on the shared phone. Karim unlocks the
  till with his PIN. 8:30 Karim pays ৳400 for milk from the drawer (pay-out, photo of the
  slip). All day: cups of tea, some on credit to regulars. 14:00 shift handover to the second
  helper. 21:00 Rahim closes: counted cash vs expected, ৳20 short, noted. He takes ৳2,000
  home (drawing). Saturday: helpers' weekly wages in cash from the drawer, one advance
  recovered.
- **Modules.** Till, Customers (dues), Expenses (pay-outs), Payroll-lite (weekly cash wages),
  Attendance (kiosk on the shared phone, optional), Home (takings, drawer, dues).
- **Connections.** Pay-outs → Expenses + drawer; wages → drawer + payroll record; dues ↔ till
  ↔ customers; everything → simple P&L ("you kept ৳…") even without full accounting on.
- **Configure.** Menu with variants (small/large), credit limits for regulars, two PINs.
  Nothing else. Interface mode: simple.
- **Transition to S1.** Triggers: adds stock tracking or a supplier on credit, hires a
  salaried cashier, passes ~5 people. Product suggests: "Track stock?", "Pay salaries
  monthly?", Starter plan.

#### S1 — Nasrin's grocery (8 people, 1 shop)

- **A month.** Daily: sales with barcodes and weights; bKash payments recorded; suppliers
  deliver on credit; low-stock list each evening. Weekly: count a shelf. Monthly: salaries
  (some bKash, some cash), supplier payments, electricity and rent, a P&L the accountant
  checks.
- **Modules.** + Inventory (units, purchases, suppliers), Payroll (monthly), Books (on, mostly
  invisible), Leave (basic), Reports (sales and margin).
- **Connections.** Purchases → supplier dues → payments from bank or drawer; sales → stock →
  cost of goods → margin; payroll → books + bank/drawer; expenses → books.
- **Configure.** Items import from Excel, suppliers, payment methods, a cashier role with a
  discount limit, Tanvir (part-time accountant) with books access only.
- **Transition to S2.** Trigger: adds a branch. Product: per-branch stock, prices and
  drawers; branch manager template with branch scope; Growth plan.

#### S2 — Two outlets (20 people, 2–3 branches)

- **A week.** Branch managers run their own drawers, staff and stock; transfers between
  branches; Nasrin compares branches every evening; customers buy at either branch with one
  dues account.
- **Modules.** Same as S1 plus branch-aware everything; Attendance with rosters; Approvals
  (refunds and pay-outs over limits).
- **Connections.** Transfers ↔ stock both ends + books per branch; branch P&L (dimensions);
  shared customers across branches; branch managers' access scoped to their branch (5.1).
- **Configure.** Branches, branch prices, branch managers, approval limits.
- **Transition to S3 or S4.** Becomes an office-style business (S3) or keeps adding
  branches (S4).

#### S3 — Farhana's 30-person agency (1–2 offices)

- **A month.** Leave and approvals, projects with time and expenses, client invoices on
  30-day terms, onboarding two joiners, policies acknowledged, payroll with tax and bonuses,
  expense claims reimbursed in payroll.
- **Modules.** People (reports-to), Attendance (hybrid), Leave, Payroll, Tasks with time,
  Documents (templates), Announcements, Approvals (chains), Invoices, Expenses (claims),
  Books, Reports (project profitability), AI.
- **Connections.** Time × salary cost → project cost; invoices → revenue per project;
  claims → approvals → payroll; leave → payroll; onboarding → tasks + documents + access.
- **Configure.** Departments, reports-to, leave policies, salary structures, approval chains,
  document templates, project and client lists.
- **Transition to S4.** Trigger: 60+ people, regional offices, an HR team.

#### S4 — A multi-branch company (100–500 people, 5–30 branches)

- **A quarter.** Regions with regional managers; HR team handles hiring and payroll for all
  branches; finance closes the books monthly with bank reconciliation; budgets per branch;
  internal audits of cash handling; rosters for hundreds of shift workers; performance
  reviews.
- **Modules.** All, with regions (branch groups), budgets, rosters at scale, audit tools,
  data exports.
- **Connections.** Branch/region dimensions everywhere; budgets vs actuals; approval chains
  by amount and region; HR changes with effective dates flow to payroll and access.
- **Configure.** Regions, positions, approval matrix, budget per branch, field visibility
  (salaries hidden from branch managers).
- **Transition to S5.** Trigger: a second legal company, or a large customer requiring
  SSO/SCIM and strict audits.

#### S5 — Mr. Chowdhury's group (3 companies, 900 people)

- **A year.** Each company keeps its own books and payroll; group finance sees consolidated
  results; shared HR directory and SSO; inter-company services billed monthly; external
  auditors get read-only access for a month; data exported nightly to their BI tool via the
  API.
- **Modules.** All, plus group layer (4.7), developer platform, audit exports.
- **Connections.** Inter-company transactions mirrored in both companies' books; group roles
  (CFO sees all books, nothing else); SCIM groups → access templates.
- **Configure.** Group, companies, group roles, SSO, SCIM, API keys, retention policies.

### 4.4 Business setup: one place to shape the business

Replace scattered settings with a **Business setup** area, organised by the business's own
words, not by module:

- **Your business**: name, type, size stage, country, currency, time zone, week, fiscal year,
  logo, address. **Business type and stage can be changed**: changing shows a preview of what
  will switch on, which defaults it would add, and what stays untouched (never deletes data).
- **Places**: branches with hours, location area, tills, price lists, stock locations.
- **People structure**: departments, positions, reporting lines, shifts.
- **Money**: payment methods, taxes, drawers and petty cash, bank accounts, chart of
  accounts, approval limits, fiscal locks.
- **What you sell and buy**: items, categories, variants, units, recipes, suppliers.
- **Time and pay**: work week, holidays, leave types, salary structure, bonuses, overtime.
- **Access**: roles, permission templates, member overrides (section 5).
- **Automations and notifications**: defaults per business type.
- **Interface mode** that actually does something: *simple* hides advanced fields and tabs
  (variants, dimensions, approval chains); *advanced* shows everything. Per workspace, with
  a per-person override.
- **Setup health**: a checklist that adapts to the stage ("you sell on credit but no
  customer has a credit limit", "two branches but no branch managers").

Every default from the configuration audit (Phase 0.2) gets a home here.

### 4.5 The connections that make it one product

To be designed in detail during Phase 2. The core flows:

```
           ┌─────────── Till / Sales ───────────┐
 Customers ◀─ credit, payments ─▶ Drawer ◀─ pay-outs, cash-in, drawings
     │                              │
     ▼                              ▼
  Dues ageing                Expenses ◀─ claims ◀─ People
     │                              │        ▲
     ▼                              ▼        │ approvals
   Books ◀────── every money movement ───────┤
     ▲                              ▲        │
 Inventory ◀─ recipes, purchases ─ Suppliers  │
     ▲                                       │
 Payroll ◀─ attendance, overtime, leave, advances, claims
     │
     └─▶ paid from bank / drawer / wallet ─▶ Books
 Tasks/Projects ◀─ time, expenses, revenue ─▶ project profitability
 Reports / Home / AI ◀─ everything, through capabilities
```

Each arrow gets: the event or call that carries it, what the user sees on both ends (links in
both directions), how a mistake on one end is corrected on the other (reversal, not delete),
and a scenario test.

### 4.6 Growth path and plans

- **Plan changes in the app**, before billing exists: the owner chooses a plan; until M5 it's
  a request the platform operator approves (or free during pilots). Limits, read-only and
  module locks already exist.
- **Suggestions, not walls**: "you have 14 people, your plan allows 15" a week before; "you
  opened a second branch — branch managers can now see only their branch".
- **Downgrades** never delete: extra modules read-only, extra branches archived, data exported.
- **Stage-aware Home and checklists** (4.4 setup health).

### 4.7 Multi-entity (S5)

Groups run several companies: one login, many workspaces exists today (switching). What S5
needs: a **group** above workspaces with shared people directory and SSO, consolidated
reports across companies, inter-company transfers, and group-level roles (a CFO who sees all
companies' books). A design question, not a quick build; may move to Phase 4.

---

## 5. Phase 2 track — Access you can shape person by person

The owner asked for "very, very highly configurable" permissions when adding a member,
without losing the safety of roles. Today: one role (built-in or custom) + one department
scope per member.

### 5.1 The model

**Effective access = role template + this person's changes, within their scopes, under their
limits.**

1. **Role templates** stay (Owner, Admin, Manager, Accountant, Cashier, Employee, custom), now
   with sensible versions per business type ("Shop manager", "Head cashier", "HR officer").
2. **Per-person changes**: grant or remove any permission for one person, on top of the role,
   without creating a custom role. Shown as a diff: "Cashier, plus *see stock*, minus *give
   credit*".
3. **Scopes per permission**, not one per person:
   - *Everything* · *These branches* · *These departments (and below)* · *Their own team*
     (needs reports-to) · *Only their own records*.
   - Example: Karim may *sell* at Gulshan and Banani, *see sales* only at Gulshan, *approve
     leave* for the Kitchen department.
4. **Limits**, with money and counts:
   - approve expenses up to ৳10,000; refunds up to ৳2,000; discounts up to 10%; voids only
     within 10 minutes of the sale; pay-outs up to ৳1,000 per shift; credit to customers up
     to their limit only.
   - Above a limit: the action becomes a request in the approvals inbox, not a refusal.
5. **Field visibility**: salaries, national IDs, cost prices and margins, customers' phone
   numbers, bank details — each can be hidden even from someone who can see the record.
6. **Time-bound access**: "acting manager while Rina is on leave, 10–20 Oct", expires itself;
   **delegation** of approvals while away.
7. **Segregation of duties** warnings: the same person able to create a supplier and pay it,
   or prepare and approve payroll; the owner can accept the risk with a reason (audited).
8. **Module access levels in plain words**: for each module, *No access · See · Use · Manage ·
   Approve*, mapped to the underlying permissions, with an "advanced" view of the raw list.

### 5.2 The screens

- **Add a member**: name → how they sign in → **start from a template** → adjust per module
  (levels, scopes, limits, hidden fields) → **preview "what Karim will see"** (a real
  rendering of their Home and menu) → invite.
- **Member's access page**: the effective permissions with where each comes from (role,
  personal change, temporary grant), history of changes, "copy access from another person".
- **Bulk**: apply a change to several people; compare two people's access.
- **View as**: owners and admins can open the app as a member (read-only, audited).

### 5.3 Engineering notes

- A permission evaluator replaces `catalog.resolve()` + `scope_department_id`:
  `can(ctx, permission, resource)` → considers role, personal grants/denies, scopes, limits,
  time windows. Services ask about a **resource** (this sale, this branch, this person), not
  only a permission.
- Tables: `member_grants` (permission, effect allow/deny, scope type, scope ids, limit,
  valid from/to), `field_policies`, `delegations`.
- Branch scope requires every relevant record to carry a branch (most do: sales, drawers,
  expenses, purchases, employees; customers don't yet).
- "Own team" requires reports-to (1B.1).
- Every existing scoped check (`in_scope`, `scope_departments`) migrates to the evaluator;
  the isolation sweep and capability parity tests extend to cover grants, scopes and limits.
- Existing roles and memberships migrate unchanged (a role with no personal changes behaves
  exactly as today).
- Performance: effective permissions computed once per request (cache by membership +
  version), as today.

### 5.4 Edge cases to design for

A person with a deny on something their role grants; a grant on a module that's switched
off; a limit in a currency the workspace changed; a temporary grant that expires mid-action;
the last person who can approve payroll going on leave; an API key made by someone whose
access later shrinks (keys already shrink with their maker — keep it so); SSO users whose
role comes from the identity provider (SCIM groups → templates).

---

## 6. Proposed Phase 3 — Go live and get paid

Can partly run in parallel with Phase 2 once Phase 1A is done.

1. **Deploy** (handbook chapter 10), on the cheapest schedule; uptime check; budget alert.
2. **Pilots**: 2–3 businesses at different stages (a stall, a shop, an office), using
   `pilot-playbook.md`; weekly visits; their findings go into the gap register with top
   priority.
3. **Billing (M5)**: Paddle for international cards; **bKash/Nagad/SSLCommerz** for
   Bangladesh (needs trade licence and merchant accounts); plan changes from 4.6 become
   self-serve; invoices in BDT with VAT if registered.
4. **Legal**: lawyer's review of terms, privacy, DPA; tax adviser on the salary tax table.
5. **Support**: WhatsApp support number, in-app help, a status page.
6. **Security before real data**: ZAP scan, penetration test, restore drill on production.

## 7. Proposed Phase 4 — Scale and reach

1. **Mobile**: installable app (PWA) with offline for the till and attendance first; push
   notifications; later native wrappers if needed.
2. **Payments and messages**: bKash/Nagad payment links on customer reminders; SMS for
   staff without smartphones; WhatsApp Business API for payslips and reminders.
3. **Integrations**: bank statement import (CSV, then bank APIs); BEFTN salary files;
   accounting export to Tally/QuickBooks; e-commerce orders into Sales.
4. **Performance at size**: stored daily totals for reports; partitioning for large tables;
   files moved from Postgres to R2; load tests at 5,000 people and 1 million sales.
5. **Multi-entity groups** (4.7) if not done in Phase 2.
6. **Assets** (laptops, machines) and **vehicles/deliveries** if pilots ask.
7. **Marketplace of presets**: business-type templates others can share (a pharmacy preset,
   a restaurant preset with recipes).

---

## 8. Order, effort and checkpoints

Rough working days for one developer with AI help; revised after Phase 0's audit.

| Phase | Sub-phase | Effort | Checkpoint (owner) |
|---|---|---|---|
| 0 | Groundwork | 2–3 d | review walkthrough screenshots and the gap register |
| 1A | Shop's money (6 screens) | 12–18 d | run a tea stall's day yourself on a phone |
| 1B | People and time (4) | 10–14 d | run a month of payroll for a 10-person shop |
| 1C | Work (4) | 6–9 d | run an agency's week |
| 1D | Seeing the business (5) | 6–8 d | check Home and Reports for each persona |
| 1E | Running the workspace (6) | 5–7 d | invite people and set up a business from scratch |
| 2 | Stages S0–S5 journeys + business setup + connections | 15–25 d | walk each stage's journey; approve transitions |
| 2 | Access you can shape | 8–12 d | add five people with different access; "view as" each |
| 3 | Go live and get paid | 5–10 d + pilots' calendar time | first paying pilot |
| 4 | Scale and reach | as pilots require | — |

**Rules that carry over:** English and Bangla everywhere; logic in services; modules never
import the AI layer; every route declares access; every tenant table has RLS; the public site
only claims what's built; `scripts/check.sh` before every push; commits as the owner, no AI
co-author lines.

**New rules:**
- No screen is "done" without its scenarios and exit criteria (1.3).
- Every link between modules is visible in both directions.
- Nothing a real business would change stays hard-coded; it gets a home in Business setup.
- Every number on screen can be explained (a link to where it came from).

---

## 9. Decisions the owner needs to make

Answer these in this file (write under each) before or during Phase 1.

1. **Order of Phase 1 clusters**: is 1A (shop) → 1B (people) → 1C (work) → 1D → 1E right, or
   should offices (1B/1C) come first for the agency market chosen in §2.0 of the first plan?
2. **Payment methods at the till**: recorded methods only (cash, bKash, Nagad, card, bank)
   for now, real integrations in Phase 4?
3. **Daily wages paid from the till**: payroll items (proper) or expenses (simple), or a
   choice per business?
4. **Market purchases with drawer cash**: inventory purchases (cost per cup) or expenses
   (simple), or a choice per item?
5. **B2B invoicing**: inside Customers, or its own module?
6. **Expense claims** reimbursed via payroll, cash, or either?
7. **Business type and stage change**: allowed any time? Who may do it (owner only)?
8. **Interface mode**: keep simple/standard/advanced and make it real, or drop it?
9. **Plan changes before billing**: free during pilots, or manual approval by you?
10. **Access model**: is the model in 5.1 what you meant? Anything missing (e.g. access by
    time of day, by device, by IP for some people only)?
11. **Multi-entity groups**: Phase 2 or Phase 4?
12. **Which pilot businesses** can you line up for Phase 3, and at which stage?

---

## Appendix A — Known gaps found so far

Verified in the code on 5 October unless marked **(verify)**.

| # | Screen | Gap | Type |
|---|---|---|---|
| A1 | Till | No pay-out, cash-in or owner-drawing action; expenses from the drawer must be recorded on the Expenses page | missing link |
| A2 | Expenses | Drawer expenses are linked to a drawer only by person + time window, not by the drawer session; Expenses doesn't show which till/shift | missing link |
| A3 | Till | "Add items" link appears only when the till has no items | confusing UX |
| A4 | Sign-up / Home | Sample items (tea, coffee, samosa, cake) aren't clearly marked as samples where they appear | confusing UX |
| A5 | Settings | Business type can't be changed after sign-up; it's only used to pick initial modules | missing feature |
| A6 | Settings | Interface mode (simple/standard/advanced) is saved but changes nothing | wrong default |
| A7 | Settings / plans | No plan change in the app (only SQL by the operator) | missing feature |
| A8 | Team / access | One role + one department scope per member; no branch scope, no per-person grants, no limits, no field visibility | missing feature |
| A9 | People | No reports-to / line manager; one branch per person | missing feature |
| A10 | Till / Sales | Cash only: no payment methods, no split payment | missing feature |
| A11 | Sales | One price per item: no variants, modifiers, or per-branch prices | missing feature |
| A12 | Customers | No branch on customers; no ageing, write-off, merge, invoices with terms | missing feature |
| A13 | Inventory | No units/pack sizes, recipes, purchase orders, expiry | missing feature |
| A14 | Approvals | Only leave and time fixes; no expense, purchase, refund or payroll approvals; no chains or thresholds | missing feature |
| A15 | Expenses | No employee claims, recurring expenses, supplier bills or project tags | missing feature |
| A16 | Books | No opening-balance wizard, bank reconciliation, branch/project dimensions **(verify dimensions)** | missing feature |
| A17 | Home | HR-shaped cards only (clock, at work, approvals, news, tasks, away); nothing about takings, the drawer, dues or stock for a shop owner | missing feature |
| A18 | Reports | HR-focused; shop reports live under Sales, not Reports | missing link |
| A19 | Tests | Books tests assumed UTC dates; fixed 5 Oct — other tests may share the assumption **(verify)** | bug risk |
| A21 | Attendance | One lateness rule per workspace; no shifts, rosters or overtime approval; a `kiosk` source exists in the database but no screen uses it **(verify)** | missing feature |
| A22 | Payroll | No pay frequencies other than monthly runs, no paid-from account, PF, gratuity, arrears or final settlement | missing feature |
| A23 | Tasks | No recurring tasks, time logs, dependencies, budgets or clients | missing feature |
| A24 | Announcements / Documents | No scheduling, expiry, must-acknowledge notices, folders, templates or private per-person documents | missing feature |
| A20 | Settings | `.env` with an empty `PLATFORM_OPERATORS` crashed start-up; fixed 5 Oct | bug (fixed) |

## Appendix B — Personas used throughout

| Persona | Business | Device | Language | Notes |
|---|---|---|---|---|
| **Rahim**, owner | tea stall, 2 helpers, Mirpur | cheap Android, shared | Bangla | cash and credit; low patience for forms; checks takings at night |
| **Karim**, helper/cashier | same stall | the shared phone | Bangla, reads slowly | needs big buttons, icons, PIN not password |
| **Nasrin**, owner | grocery, 8 staff, 2 branches | phone + laptop | Bangla and English | stock, suppliers, credit customers, monthly salaries |
| **Tanvir**, accountant | works for Nasrin part-time | laptop | English | books, VAT, payroll, reconciliations |
| **Farhana**, HR manager | 30-person agency, Gulshan | laptop | English | leave, payroll, onboarding, documents, approvals |
| **Arif**, team lead | same agency | phone | English | tasks, approvals for his team only |
| **Mr. Chowdhury**, CFO | group of 3 companies, 900 people | laptop | English | consolidated books, strict access, SSO, audits |
