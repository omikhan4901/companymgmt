# CompanyMgmt — the next implementation plan

**Version 2, revised 6 October 2026 after the owner's review.** Version 1 (5 October) and
the owner's inline comments are in git history (commit `5c8a372`); every comment is folded
into this version, and [§0.2](#02-what-changed-after-the-owners-review) shows where each
one went.

**The goal is a finished product, not an MVP.** Every module must be excellent on its own,
much better together, work end to end, and handle every unhappy path. The owner should
eventually run most of the business by talking to the assistant.

The work is organised as:

- **Phase 0 — Groundwork.** Audits, test tooling, baselines, feature flags.
- **Phase 1 — Foundations, then every module done properly.** First the things every module
  stands on (the module marketplace, business setup, the access engine, product-wide
  standards); then each module taken on its own, its real use cases and edge cases, built to
  work standalone and connected.
- **Phase 2 — One business across its whole life.** Follow businesses from a tea stall to a
  group of companies — and back down, sideways and out — making the modules work together at
  every stage. Includes groups of companies and the assistant as a primary interface.
- **Cross-cutting tracks** that run alongside: data migration, compliance, backups and
  portability, multi-currency, the developer platform, performance and observability,
  WhatsApp and SMS, printing, private integrations.
- **Phase 3 — Go live and get paid. Phase 4 — Scale and reach.**

Where it says **"today"**, that's what the code does now, checked on 5–6 October; items
marked **(verify)** get confirmed in Phase 0 before anything is built on them.

---

## Contents

0. [Why this plan, and what changed after the review](#0-why-this-plan-and-what-changed-after-the-review)
1. [The product model: base modules and a marketplace](#1-the-product-model-base-modules-and-a-marketplace)
2. [Product-wide standards](#2-product-wide-standards)
3. [How we'll work](#3-how-well-work)
4. [Phase 0 — Groundwork](#4-phase-0--groundwork)
5. [Phase 1 — Foundations](#5-phase-1--foundations)
6. [Phase 1 — Every module done properly](#6-phase-1--every-module-done-properly)
7. [Phase 2 — One business across its whole life](#7-phase-2--one-business-across-its-whole-life)
8. [Phase 2 — Access you can shape person by person](#8-phase-2--access-you-can-shape-person-by-person)
9. [Phase 2 — The assistant as a primary interface](#9-phase-2--the-assistant-as-a-primary-interface)
10. [Cross-cutting tracks](#10-cross-cutting-tracks)
11. [Phase 3 — Go live and get paid](#11-phase-3--go-live-and-get-paid)
12. [Phase 4 — Scale and reach](#12-phase-4--scale-and-reach)
13. [Honest estimates and checkpoints](#13-honest-estimates-and-checkpoints)
14. [Decisions: made and still open](#14-decisions-made-and-still-open)
15. [Appendix A — Known gaps](#appendix-a--known-gaps) · [Appendix B — Personas](#appendix-b--personas)

---

## 0. Why this plan, and what changed after the review

### 0.1 What went wrong in the first build

The first build (M1–M11) was planned **feature by feature**: does the till sell, do the
books balance, does leave respect the balance. Each works and is tested. What was never
planned is **how a real business lives in the product**:

- **Modules are islands joined by events.** Money taken from the till for milk is recorded
  in Expenses with "paid from: drawer"; the drawer finds it by matching the cashier and the
  time. The till has no "pay out" button, and Expenses doesn't show which till or shift.
- **Configuration was hard-coded for the first ten minutes, then forgotten.** The business
  type picks modules once and can't be changed; "interface mode" is saved and does nothing;
  sample items look like built-ins; the till only links to "add items" when there are none.
- **There's no path to grow, shrink or change.** Plans can't be changed in the app; nothing
  helps a stall open a branch, an agency downsize, or a seasonal business wind down.
- **Access is role-shaped, not person-shaped.** One role and one department scope per member.
- **Tests proved rules, not journeys**, and the assistant was treated as one screen rather
  than the way owners should eventually work.

### 0.2 What changed after the owner's review

| Owner's point | Where it's handled now |
|---|---|
| Not linear by business type: everyone picks the modules they want; business types are only presets | §1 (base + marketplace), §6 order by dependency, not by market |
| "If anything can be a module, it's a module"; independent but much better together; merge/split freely | §1.3 catalogue, §1.4 merges, §1.5 better-together matrix, §1.6 rules |
| Base modules always included: Users, Access, Business, Home | §1.2 |
| A "Marketplace" to add modules; requires/conflicts rules | §1.6, §5.1 |
| Customers becomes **CRM** (customers, transactions, payments — no lead generation) | §1.3, §6 CRM |
| 11th edge-case axis: security | §3.2 |
| Exit criteria: accessibility, 2 s on 3G, localized errors with recovery, printing | §2, §3.3 |
| Testing: isolation everywhere incl. AI/reports/exports, a11y, performance, offline, real browser interaction tests | §3.4 |
| Phase 0: technical-debt audit and a ZAP baseline | §4 (0.8, 0.9) |
| Books: plain-language P&L through the assistant; immutability; auditor export | §6 Books, §9, §10.2 |
| Kiosk security, stolen tablets, fingerprints | §6 Attendance |
| Payroll compliance: statutory registers, minimum wages, overtime caps, tax on by default | §6 Payroll, §10.2 |
| Home as a personal command centre: widgets, quick actions, the assistant | §6 Home, §9 |
| Reports: saved, shared, a builder, goals | §6 Reports |
| Sign-up: mobile-first, "what else can you do", demo mode without signing up | §6 Sign-up |
| Missing stages: seasonal, pivot, closure, downsizing | §7.3, §7.6 |
| Access like Discord: personal overrides beat the role | §8.1 |
| A person can hold several roles | §8.1 point 1 (each role with its own scope) |
| Branding: logo, banner and customization per business | §5.5 |
| "Access by time/device/IP — what?" | explained in §8.1 (6) and §14.2 |
| Estimates are optimistic; new standards need line items | §13 (re-estimated, roughly 2.5×) |
| bKash/bank APIs for one company privately | §10.9 |
| Business type change: any time, new plan billed from next month, owners only (several owners allowed) | §7.5, §14.1 |
| Interface mode: make it real | §5.2 |
| Plan changes before billing: free for pilots via an invitation | §7.5, §11 |
| Groups of companies as fast as possible | §7.7 moved into Phase 2 core |
| Pilots: any business | §11 |
| AI is not optional; owners will mostly talk to the assistant | §9 (own track) |
| Error UX standards | §2.1 |
| Data migration and cut-over | §10.1 |
| Audit trail and compliance | §10.2 |
| Backup, disaster recovery, portability | §10.3 |
| Module dependency graph and marketplace | §1.6 |
| Downgrade and business failure path | §7.6 |
| Multi-currency | §10.4 |
| API and developer platform | §10.5 (much already exists; what to extend) |
| Performance and observability | §2.3, §10.6 |
| Accessibility | §2.2 |
| More than two languages | §2.5 |
| Tenant isolation testing | §3.4 (extends the existing sweep) |
| Feature flags and staged rollout | §4 (0.10), §10.7 |
| The assistant as a first-class interface | §9 |
| Frontend interaction tests | §3.4 |
| WhatsApp as a channel | §10.8 |
| Printing | §2.4 |

---

## 1. The product model: base modules and a marketplace

### 1.1 Principles

1. **If something can be a module, it's a module.** A business adds what it needs, the way
   it would add apps to a phone. Business types (tea stall, office, factory…) are only
   **presets**: a bundle of modules and sensible defaults, all changeable later.
2. **Every module is excellent on its own.** Someone who only wants payroll gets a payroll
   product that beats a spreadsheet and the alternatives, without being pushed into others.
3. **Every pair of modules is better together than apart**, visibly: each connection removes
   double entry, adds a number nobody could see before, or catches a mistake. That is the
   reason to add the next module.
4. **A module that is useless alone comes bundled** with what it needs (§1.6 rules).
5. **Turning a module off never deletes data.** History stays readable, reports for past
   periods still work, and turning it on again picks up where it left off.
6. **The assistant spans everything.** It isn't a module you add; it grows with each module
   you add (§9).

### 1.2 Base modules (always on, free on every plan)

| Base module | What it is | Today |
|---|---|---|
| **Business** | the business itself: name, type/preset, stage, places (branches), structure (departments, positions), money settings, calendars, the module marketplace, Business setup | spread across Settings; no marketplace screen |
| **Users** | people who sign in: accounts, invitations, join links, staff without email, devices, sessions, passkeys, company sign-in | exists (Team, Account) |
| **Access** | roles, templates, personal overrides, scopes, limits, field visibility, approvals engine, audit log | roles + one department scope; approvals only for leave and time fixes |
| **Home** | each person's command centre: widgets from every module, quick actions, the assistant, notifications | fixed HR-shaped cards |

Also always present but not "modules": **Notifications**, **Help**, **the assistant** (§9),
**Reports framework** (each module adds its reports), **Data rights** (export, delete,
restore).

**Decision needed (§14.2):** "Users" and **People** (HR profiles) are different things — a
cashier may sign in without an HR record in a shop that doesn't use HR, and a factory may
keep HR records for workers who never sign in. Today every member automatically gets a
People profile. Proposal: People becomes a marketplace module; Users stays base.

### 1.3 The module catalogue (rethought)

| Module | Standalone value (alone it must beat a spreadsheet) | Requires | Today |
|---|---|---|---|
| **People** (HR records) | employee files, org chart, documents per person, employment history, reminders (contracts, probation) | — | People |
| **Attendance** | clock in/out with location, kiosk, shifts and rosters, timesheets, lateness | People | Attendance |
| **Leave** | requests, balances, calendar, policies, approvals | People | Leave |
| **Payroll** | salaries, runs, payslips, statutory registers, bank/wallet files | People | Payroll |
| **Point of Sale** | the till, drawers, receipts, offline, tills and PINs, payment methods | — | Sales & POS |
| **CRM** | customers, their transactions and dues, payments, statements, reminders, invoices and quotes for B2B (no lead generation) | — | Customers & dues |
| **Purchasing** *(new, split)* | suppliers, purchase orders, supplier bills and payments, what you owe | — | inside Inventory |
| **Inventory** | stock per place, units, recipes, counts, transfers, valuation, expiry | — | Inventory (requires Sales today) |
| **Expenses** | spending, receipts, petty cash, claims, recurring bills | — | Expenses |
| **Books** | double-entry accounting that keeps itself, reports, tax returns | — (useful alone as manual books) | Accounting |
| **Projects & Tasks** | projects, boards, recurring tasks, time logs, budgets | — | Tasks & projects |
| **Communication** *(merged)* | announcements, notices to acknowledge, scheduled posts | — | Announcements |
| **Documents** | company documents, policies, templates, private files per person, expiry reminders | — | Documents |
| **Automations** | rules that react and remind | — | Automations (always on today) |
| **Assets** *(new)* | equipment and who holds it, maintenance, depreciation | — | none |
| **Developer platform** | API keys, webhooks, company sign-in, SCIM | — | spread in Settings |

### 1.4 Proposed merges and splits (owner decides, §14.2)

- **Split Purchasing out of Inventory.** A restaurant that doesn't count stock still has
  suppliers and bills; a shop that counts stock buys from suppliers. Both modules stand alone;
  together, received purchase orders add stock automatically.
- **Inventory no longer requires Point of Sale.** A warehouse or factory tracks stock without
  selling at a till.
- **Customers becomes CRM** and absorbs invoices and quotes (owner's decision).
- **Announcements becomes Communication**, ready for notices that must be acknowledged,
  scheduled posts and, later, WhatsApp broadcasts. Documents stays separate (it's a library,
  not a feed).
- **Approvals moves into Access (base)** as an engine every module uses, not a module.
- **Reports becomes a framework in the base**, with each module contributing its reports.
- **Considered and rejected:** merging Attendance and Leave (each is useful alone: many shops
  track attendance without formal leave), merging Expenses into Books (most owners want
  Expenses without accounting).

### 1.5 Better together: what each connection adds

The incentive to add the next module. Each line becomes a scenario test in Phase 2.

| When you have… | …and add | You get |
|---|---|---|
| Point of Sale | Inventory | stock moves with every sale, margin per item, low-stock alerts, recipes turn cups into milk and sugar used |
| Point of Sale | CRM | credit sales, dues, statements, reminders, a customer's history at the till |
| Point of Sale | Expenses | pay-outs from the till become expenses with their shift; the drawer count includes them |
| Point of Sale | Payroll | daily wages paid from the drawer, recorded once |
| Point of Sale | Attendance | cashiers clock in and open their drawer in one step; sales per person per shift |
| Purchasing | Inventory | received orders add stock at the right cost |
| Purchasing | Expenses | supplier bills that aren't stock become expenses |
| Any money module | Books | everything posts itself; P&L, balance sheet and tax returns with no bookkeeping |
| Attendance | Payroll | overtime, absences and late rules flow into pay |
| Leave | Payroll | unpaid leave, encashment, maternity rules in pay |
| Leave | Attendance | absences are explained; rosters show who's away |
| People | anything | one profile shows a person's attendance, leave, pay, tasks, sales, claims, assets |
| Projects & Tasks | Payroll + Attendance | time × cost per hour = project cost |
| Projects & Tasks | CRM | invoices per project = revenue; project profitability |
| Expenses | Projects | costs per project or client |
| Documents | People | private files on each profile; templates filled from profiles (offer letters) |
| Communication | Attendance | notices to one shift; acknowledgements tracked |
| Assets | People + Payroll | who holds what; deductions for lost items at final settlement |
| Automations | anything | rules across modules (dues overdue → reminder; drawer short → notify owner) |

### 1.6 The rules: requires, enhances, conflicts, standalone mode

Formalised in code as a module manifest (one per module):

- **requires**: cannot be enabled without (Payroll → People).
- **enhances**: optional connections switched on automatically when both are present
  (Point of Sale + Inventory), each with its own setting to turn off.
- **conflicts**: cannot be on together (none expected yet; the mechanism exists for later,
  e.g. two payroll engines for different countries).
- **standalone mode**: what the module does when its usual partners are absent (Payroll
  without Attendance: overtime entered by hand; Books without money modules: manual journal;
  Inventory without Purchasing: stock received by adjustment with a cost).
- **plan availability**: which plans include it; per-module pricing is a Phase 3 decision.
- **data when off**: read-only history, still in exports and the assistant's answers for past
  periods.
- **switching**: enabling shows what it adds and which connections light up; disabling shows
  what stops (and that nothing is deleted). Billing changes from the next month (owner's rule).

### 1.7 Presets

A preset = modules on + defaults (roles, leave types, categories, chart of accounts, tax
presets, Home layout, first-day flow, interface mode). Presets: tea stall/food stall,
restaurant, grocery/retail, pharmacy, office/agency, factory, NGO, other. Choosing a new
preset later shows a diff and never removes data.

---

## 2. Product-wide standards

Every screen follows these; Phase 1 Foundations builds the shared pieces once.

### 2.1 Errors and unhappy paths

- **Three kinds of message, used consistently:**
  *inline* (a field is wrong: next to the field, in the person's language, saying how to fix
  it); *blocking* (the action can't happen: a dialog that explains why and offers the way
  forward — "Your plan allows 15 people. Upgrade, or remove someone"); *toast* (only for
  success, or for a background failure with a "see details" link that stays in the
  notification list).
- **Every error message is translated** and maps to a stable code; no raw server text.
- **Retry or keep:** network failures keep the person's input and offer *Try again*; offline
  actions go to a visible queue with *Send now* / *Discard*.
- **Partial failure:** long operations (payroll finalize, imports, backfills, bulk edits) run
  as **jobs** with progress, are all-or-nothing in one transaction where possible, and
  otherwise record exactly what finished and resume safely (idempotent steps). The person sees
  "38 of 40 done, 2 need attention" with links.
- **Undo** where it's safe (archive, move, mark read, send to the bin for 30 days); **reverse**
  where it's money (never delete posted records); **confirm** only for irreversible actions.
- **Graceful degradation:** if AI, email or a payment provider is down, the rest works and a
  banner says what's affected.
- An **error catalogue** (`docs/standards/errors.md`) lists every code, its message in both
  languages and the recovery path; a test fails if a code has no message.

### 2.2 Accessibility

Today the browser tests run axe (WCAG 2.2 AA) and a no-sideways-scroll check on every page
they visit; the standard below makes it explicit and wider.

- Every screen keyboard-navigable in a logical order, with visible focus.
- Every control labelled for screen readers; actions announced ("Sale saved, ৳120").
- Contrast AA in both themes and every accent; text resizable to 200% without loss.
- Touch targets at least 44 px; the till and kiosk at 56 px+ with icons beside words for
  people who read slowly.
- Plain language, short sentences, numbers formatted for the person's language.
- Manual checks per screen with a screen reader (TalkBack on Android, NVDA on Windows).

### 2.3 Performance budgets

- Every screen usable within **2 seconds on a slow 3G phone** with realistic data (a year of a
  busy shop, 500 people); the till's actions under 300 ms locally (offline-first).
- API p95 under 300 ms for reads and 600 ms for writes at the S4 volume; reports either fast
  or computed in the background with a "ready" notification.
- Budgets checked in CI-equivalent (`check.sh`) with seeded volume data (§3.4).

### 2.4 Printing

What prints: receipts (58 and 80 mm thermal), A4/A5 invoices and quotes, payslips, statements,
purchase orders, statutory registers, reports, shelf labels and barcodes, kiosk QR cards.
Standards: a print preview for every printable; both languages with the right fonts;
the business's logo, address, tax number and footer from Business setup; page numbers and
totals carried over pages; works from a phone (share as PDF) and a desktop printer;
Bluetooth/USB thermal printers in Phase 4.

### 2.5 Languages: built for many, shipped with two

Ship English and Bangla; build so a third is a translation file, not code: a language
registry, per-person language, per-business default, number and date formats per language,
fonts for each script in PDFs, emails and receipts, right-to-left support for Urdu/Arabic
later. Candidates after launch: Hindi and Urdu (workers in garment factories), Arabic (staff
abroad). Chittagonian and Sylheti are mostly spoken, not written, so they're better served by
voice in the assistant (§9) than by translation files.

### 2.6 Security on every screen

The 11th edge-case axis (§3.2) applies to every screen; the platform already has the
foundations (row-level security, the isolation sweep, CSP, rate limits, upload checks).

### 2.7 Explainable numbers

Every number links to where it came from: a total to its lines, a P&L figure to its journal
entries, a balance to its ledger, a payslip line to the attendance that produced it.

---

## 3. How we'll work

### 3.1 The loop for every module and every journey

1. **Read** the module and its API as they are today.
2. **Scenarios first**, per persona (Appendix B), in Bangladesh's reality.
3. **Edge cases** along the eleven axes (§3.2).
4. **Classify** findings: *bug*, *missing link*, *missing feature*, *confusing UX*,
   *wrong default*, *needs a decision*; record them in `docs/gaps.md`.
5. **Owner review** of scenarios and decisions (short, async, in the plan files).
6. **Standalone and connected**: design what the module does alone and with each partner
   (§1.5–1.6).
7. **Tests first**: API rules, browser interaction tests, both languages, phone and desktop.
8. **Build** behind a feature flag (§10.7).
9. **Walk it** as each persona, in Bangla and English, on a phone, with a screen reader.
10. **Document**: handbook, help articles, the assistant's knowledge of the module.
11. **Done** when the exit criteria (§3.3) hold; flag turned on for pilots, then everyone.

### 3.2 The eleven edge-case axes

| Axis | Examples of what to try |
|---|---|
| **Time** | midnight in Dhaka vs UTC; month and year end; leap day; a shift across midnight; a sale at 23:59 with the drawer closed at 00:05; backdated entries; locked periods; Friday weekends; Ramadan hours; daylight saving for branches abroad |
| **Money** | rounding to the poisha and to the taka; inclusive vs exclusive and compound tax; discounts on top of tax; refunds of discounted items; very large, zero and negative amounts; change given; partial payments and overpayment; currencies (§10.4) |
| **Quantity** | fractions (0.5 kg, 250 ml); units vs packs; negative stock; selling what was never received; returns of more than sold; wastage; staff meals |
| **People** | someone who left; on leave; in two branches; a manager who is also staff; the owner as a cashier; staff without email; same names; Bangla-only names |
| **Permissions** | each role and template; personal overrides; a scoped manager outside their scope; an API key; a till PIN session; a member removed mid-session; the last owner; limits at the boundary |
| **Concurrency** | two cashiers on one drawer; two tabs editing one thing; double-clicks; the same offline sale twice; a payroll run recomputed while a salary is edited |
| **Connectivity** | offline at the till; a request that timed out but succeeded; slow 3G; the app open overnight; a refresh mid-form; the server dying mid-job |
| **Volume** | 5 vs 50,000 records; a 300-line purchase; a 2,000-person payroll; a year on a report; long names; 50 branches |
| **Language and devices** | Bangla digits in amounts; mixed scripts; right-to-left text pasted in; a 360 px phone; a shared tablet; 58 and 80 mm printing; screen readers |
| **Lifecycle** | a module off and on again; the plan dropping to Free; restored from export; sample data removed after real data; a branch closed; the business downsizing or closing |
| **Security** | injection in search and text fields; script in names and notes (XSS); cross-site requests on state changes; another tenant's ids (IDOR); malicious uploads (receipts, documents, imports); brute force on sign-in and PINs; session fixation and leftovers on shared devices; what the browser console and the raw API reveal; the assistant asked to reveal data the person can't see |

### 3.3 Exit criteria for a module or screen

- Every accepted scenario works end to end, standalone and connected, for every persona.
- Every edge case has a test or a written reason why not.
- Links to other modules exist in both directions; every number is explainable (§2.7).
- Nothing a real business would change is hard-coded; settings are reachable from the screen.
- Empty states teach; sample data is labelled; first use is guided.
- **Errors** follow §2.1: localized, with a recovery path, no disappearing red toasts.
- **Accessibility** per §2.2, including a manual screen-reader pass.
- **Performance** within the §2.3 budget on 3G with realistic volume.
- **Printing** per §2.4 wherever the screen has something to print.
- **Security** axis checked; isolation tests cover every new route, report, export and
  assistant capability.
- The assistant can answer questions about the module and (where allowed) act on it (§9).
- Help article and handbook updated; `E2E=1 scripts/check.sh` passes.

### 3.4 Testing additions

- **Scenario tests**: long, story-like API tests per persona in `api/tests/scenarios/`.
- **Browser interaction tests for every critical flow** (not only screenshots): selling,
  paying out, closing a drawer, approving, running payroll, inviting with custom access —
  desktop and phone, both languages.
- **Tenant isolation everywhere**: the existing sweep calls every id route as another
  workspace; extend it to list endpoints, reports, exports, search, webhooks, the assistant's
  answers and tool calls, and error messages (no other tenant's names or ids leaking into
  text). A test creates two tenants with overlapping names and checks every surface returns
  nothing from the other.
- **Accessibility** per screen: axe in Playwright (exists) plus keyboard-only runs of each
  critical flow and a manual screen-reader checklist.
- **Performance regression**: seeded volume datasets (10k sales, 500 people, 50k stock
  movements); key pages and endpoints timed against budgets.
- **Offline resilience**: drop the network mid-sale, mid-payroll-step, mid-import; kill the
  server mid-job; check nothing is lost or doubled.
- **Clock control**: freeze "now" in any zone (the 5 October books-test failure was a time
  zone assumption).
- **Persona seeds**: `scripts/seed_persona.py <persona>` for walking through by hand.
- **Visual walkthrough** screenshots per persona, language and size for the owner.
- **Security**: a ZAP baseline per release; tests for each security-axis case.

---

## 4. Phase 0 — Groundwork

| # | Task | Output |
|---|---|---|
| 0.1 | **Gap register** `docs/gaps.md`, seeded from Appendix A | the single list Phase 1 and 2 burn down |
| 0.2 | **Configuration audit**: every hard-coded default and preset; can an owner see/change it, where | table in `docs/gaps.md`; feeds Business setup |
| 0.3 | **Cross-module map as it is today**: events, listeners, reads, links | handbook diagram |
| 0.4 | **Persona seeds** and scenario-test scaffolding | `scripts/seed_persona.py`, `api/tests/scenarios/` |
| 0.5 | **Clock control** in tests | fixture |
| 0.6 | **Walkthrough screenshots** per persona | folder for the owner |
| 0.7 | Confirm or strike every **(verify)** item | updated Appendix A |
| 0.8 | **Technical-debt audit**: service isolation; the outbox (at-least-once delivery exists; add a dead-letter view and alerts for events that exhausted their 8 attempts); database indexes for the volume axis; the browser's offline sale queue (today `localStorage`: survives reloads, not storage clearing; consider IndexedDB with a visible queue); long operations as resumable jobs | a short report with fixes ranked |
| 0.9 | **Security baseline**: OWASP ZAP scan of the current app locally; fix anything high | report + fixes |
| 0.10 | **Feature flags**: per-workspace and per-person flags managed by platform operators, used to ship modules to pilots first | flags in the platform and the web app |
| 0.11 | **Error catalogue** skeleton and the shared error components (§2.1) | `docs/standards/errors.md`, components |
| 0.12 | **Volume datasets** for performance budgets | seed scripts |

---

## 5. Phase 1 — Foundations

Everything in §6 stands on these, so they come first.

### 5.1 The module marketplace

- Module manifests in code (§1.6), replacing `catalog.MODULES`.
- A **Marketplace** screen: every module with what it does alone, what it adds to the
  modules you have, its plan, and one-tap enable/disable with a preview of effects.
- The rules engine: requires, enhances (each connection with its own switch), conflicts,
  standalone mode, data when off.
- Presets rebuilt as bundles (§1.7); changing preset shows a diff.
- "What else can you do?" suggestions on Home based on what the business does (§6 Home).

### 5.2 Business setup and a real interface mode

- One **Business setup** area organised in the business's words (your business, places,
  people structure, money, what you sell and buy, time and pay, access, automations), with
  every default from the configuration audit given a home.
- **Interface mode made real** (owner's decision): *simple* hides advanced fields, tabs and
  options (variants, dimensions, approval chains, accounting jargon) and uses bigger controls;
  *standard* is today's; *advanced* shows everything. Per business with a per-person override,
  and every screen declares which of its parts belong to which mode.
- **Setup health**: a checklist that adapts to the modules and stage.

### 5.3 The access engine

Built early because every module's permissions depend on it; full design in §8. Includes the
**approvals engine** (chains, thresholds, delegation) that modules register request types with.

### 5.4 Shared components for the standards

Errors (§2.1), jobs with progress, print preview and layouts (§2.4), widgets for Home, the
explain-this-number link (§2.7), language registry (§2.5), feature flags (§4 0.10).

### 5.5 Branding and customization

Every business should feel the product is *theirs*. Today there's none of this: no logo, no
banner; the accent colour is a per-device preference, not the business's.

(Not to be confused with the **Assets** module, which is equipment. Brand files live in the
Business base module, under Business setup → *Your brand*.)

**Brand**
- **Logo** (square and wide versions), **banner/cover image**, **brand colour** chosen from
  palettes that stay readable in light and dark mode (contrast checked automatically, as
  today's accents are), business name in English and Bangla, tagline.
- Where it appears: the app header and sign-in page for the business's staff, Home's banner,
  the installable app's icon and splash screen (PWA), receipts, invoices, quotes, payslips,
  statements, purchase orders, reports, emails, WhatsApp templates (where allowed), join links
  and QR cards, the demo-free public business card (`/v1/public/workspace` exists today).
- **Per-branch overrides**: a branch's own address, phone, receipt footer, or sub-brand (a
  group running "Cha Ghor" and "Cha Ghor Express").
- Files: images checked by content and size, resized into the sizes each place needs, stored
  in R2 (not the database), served from the business's address.

**Documents and messages**
- **Templates** for receipts (58/80 mm), invoices, quotes, payslips, letters (offer,
  appointment, experience), statements: choose a layout, show/hide fields, header and footer
  text in both languages, terms and notes, signature images.
- **Numbering series**: prefixes and sequences per branch and year (INV-GUL-2026-0001).
- **Email sender name** and reply-to per business; branded email layout.

**The words and the shape of the business**
- **Custom labels**: rename things in the business's own words ("Outlets" for branches,
  "Members" for employees, "Shift" for drawer session), in both languages.
- **Custom fields** on people, customers, suppliers, items, assets, projects (text, number, date,
  choice, file), usable in filters, reports, imports, templates and the assistant.
- **Custom lists**: categories, reasons (void, wastage, leave), tags.
- **Default views**: column choices and sorting per list, saved per person or pushed by owners.

**Addresses and white-label (by plan)**
- The business's own address `<slug>.companymgmt.app` (reserved and checked today; needs
  wildcard DNS) with its logo on the sign-in page.
- **Custom domain** (`hr.theircompany.com`) and **white-label** (no CompanyMgmt branding in
  the app, emails and documents) for higher plans — a pricing decision (§14.2).

**Edge cases.** A huge or transparent logo; a logo with text that's unreadable in dark mode; a
brand colour too light for contrast (offer the nearest accessible shade); a Bangla business
name longer than the receipt width; changing the logo after 10,000 receipts (old receipts
reprint with the logo they were issued with? decision: reprints show the logo at the time,
stored per document); a banner on a 360 px phone; a branch sub-brand inside a group; custom
labels that collide with built-in words; custom fields deleted while used in a report.

---

## 6. Phase 1 — Every module done properly

### 6.0 Order

**By dependency, not by market** (owner's decision: shops and offices matter equally). Each
module is first made excellent **standalone**, then its connections to modules already done
are built and tested. Order:

1. **People** (many others link to it) and **Users/Access screens** on the new engine
2. **Point of Sale**, **Expenses**, **CRM**, **Purchasing**, **Inventory**, **Books**
3. **Attendance**, **Leave**, **Payroll**
4. **Projects & Tasks**, **Communication**, **Documents**, **Assets**
5. **Home**, **Reports**, **Automations**, **Notifications** (they show everything above)
6. **Sign-up, first day, demo mode, help and the public site**

Each module below has: purpose, today, real scenarios, links to build, edge cases, likely
build items, and (where the owner commented) additions. Section names keep their v1 numbers
(1A.1, 1B.2…) so the owner's notes still line up.

### 6.1 Money in and out (Point of Sale, Sales, Expenses, CRM, Inventory, Purchasing, Books)

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

**Decided.** bKash, Nagad, card and bank transfer are *recorded* payment methods now; real
integrations can be switched on per business later (§10.9).
**Still open (§14.2).** Variants before per-branch prices? Is owner drawing visible to
managers?

**Standalone vs connected.** Alone: a till with items, drawers and a simple daily summary.
With CRM: credit and dues. With Inventory: stock and margin. With Expenses: pay-outs. With
Payroll: wages from the drawer. With Books: everything posted.

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

#### 1A.4 CRM — customers, transactions and payments (`/app/customers`, renamed)

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

**Likely build items.** Ageing and overdue list; write-off; merge duplicates; **quotes and
invoices with terms** for B2B (decided: inside CRM); customer groups and price lists;
contacts per business customer; a customer's full history across modules (sales, invoices,
payments, projects); SMS/WhatsApp reminders (§10.8).

**Scope (owner's decision).** CRM covers customers, their transactions, invoices and
payments. It does **not** do lead generation, pipelines or marketing campaigns.

**Standalone vs connected.** Alone: a customer book with invoices, payments and statements
(an agency that never uses a till). With Point of Sale: credit at the till. With Projects:
invoices per project. With Books: receivables and revenue posted.

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

**Likely build items.** Units and pack sizes; recipes / bill of materials; batches and expiry
(optional per item); reorder suggestions; stock valuation report matching the books.
Purchase orders, supplier bills and supplier returns move to **Purchasing** (1A.7).

**Standalone vs connected.** Inventory no longer requires Point of Sale (a warehouse or
factory counts stock without a till). Alone: items, places, counts, transfers, adjustments
with a cost. With Point of Sale: stock moves with sales. With Purchasing: received orders add
stock at cost. With Books: stock value on the balance sheet.

#### 1A.7 Purchasing (new module, split from Inventory)

**Purpose.** Know what you've ordered, what you owe suppliers, and pay them on time.

**Today.** Suppliers, purchases (received, with input tax and amount paid) and supplier
payments live inside Inventory and require stock tracking.

**Scenarios.** A restaurant that doesn't count stock still gets a monthly bill from its
gas supplier; a grocery orders 40 items, receives 36 this week and 4 next week; a supplier
gives 30 days' credit; a damaged carton goes back to the supplier; the owner wants "who do I
owe, and when is it due?"

**Build.** Suppliers with terms; purchase orders (draft → sent → partly received →
received → closed); supplier bills (from an order or standalone); payments from bank,
drawer or petty cash; supplier returns and credit notes; supplier statements; due-date
reminders; import price lists.

**Standalone vs connected.** Alone: orders, bills and what you owe. With Inventory: receiving
adds stock. With Expenses: non-stock bills appear as expenses. With Point of Sale: pay a
supplier from the drawer. With Books: payables posted.

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

**Likely build items.** Opening balances; bank reconciliation; dimensions (branch, project);
fixed assets and depreciation (with Assets); "where did this number come from" drill-down
everywhere.

**Added after review.**
- **The assistant presents the books** (§9): "Did I make money this month?" gets a formatted
  answer in plain words with drill-down links, instead of a separate simplified screen. Books
  supplies exact numbers through capabilities; the assistant explains them.
- **Immutability:** posted journal entries are never edited or deleted, only reversed; the
  database enforces it (append-only, as the audit log already is), and corrections show both
  the original and the reversal.
- **Auditor export:** the full journal with timestamps, who posted each entry and from which
  source, in a portable format (CSV/Excel plus a signed manifest), and a time-limited
  read-only **auditor access** role (§8).

---

### 6.2 People and time

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

**Added after review: kiosk security.**
- **Locked-down mode:** a kiosk is a registered device (like a till) that opens only the
  clock-in screen: no menu, no links into the app, no back navigation to other pages; leaving
  kiosk mode needs an owner or manager PIN. Installed as an app (PWA) in full-screen, so
  there's no address bar; on Android the owner can also pin the screen (OS feature).
- **Nothing to steal on the device:** the kiosk holds only its own device token; no owner
  session. Revoking the device from Business setup ends it immediately (as tills do today).
  "Wipe" means revoke plus clearing its local data on next contact; a stolen tablet that never
  reconnects has nothing useful on it.
- **Abuse limits:** PIN lockouts per person and per device; buddy-punching checks (a photo at
  clock-in, optional; the same person clocking in on two devices).
- **Fingerprints:** browsers can't read fingerprint sensors directly, but **passkeys** use
  the phone's fingerprint or face unlock, and the product already supports passkeys. A kiosk
  passkey per worker on a shared tablet is limited by how many passkeys a device stores;
  realistic options are (a) each worker's own phone with a passkey (fingerprint) clocking in at
  the branch, (b) the shared kiosk with PIN or QR card. To test with real devices in Phase 1.

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

**Added after review: compliance is not optional.**
- **Statutory registers** a labour inspector can ask for, generated from the data: wage
  register, attendance register, leave register, overtime register, service book entries, in
  the formats the Bangladesh Labour Act 2006 and Labour Rules 2015 expect.
- **Rules enforced or warned:** minimum wages by sector (a table the owner can update, with
  the gazette date it reflects); overtime caps (warn above the legal daily and weekly limits);
  maternity leave and benefit; festival bonus norms; gratuity formula on leaving.
- **Tax deduction at source on by default** for salaried staff above the threshold, using the
  current income tax slabs, with the owner able to override or switch off. **Condition:** the
  slabs and every statutory rule above are checked by a tax adviser and a labour lawyer
  before release, each table shows "last checked on … against …", and the product warns when
  a new Finance Act is due (July). Shipping wrong tax by default is worse than shipping it
  off; the check makes default-on safe.
- Detail in §10.2.

---

### 6.3 Work

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
clients; guest access (with §8); templates.

#### 1C.2 Communication (was Announcements, `/app/announcements`)

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
approve from notification/email links, a history per request, and the limits from §8.1.

---

#### 1C.5 Assets (new module)

**Purpose.** Know what equipment the business owns, where it is, who holds it, and what it's
worth.

**Scenarios.** A laptop given to a new designer and returned when they leave; a deep freezer at
a branch that needs servicing every 6 months; a delivery motorbike with insurance renewal; the
accountant depreciating a ৳80,000 fridge over 5 years.

**Build.** Asset register (tag, category, place, holder, purchase cost and date, warranty);
assign and return with signatures (acknowledgements); maintenance schedules and history;
reminders (insurance, service, warranty end) via Automations; depreciation posted to Books;
lost/damaged assets at final settlement (with Payroll); QR labels to print.

**Standalone vs connected.** Alone: the register and reminders. With People: who holds what on
each profile; offboarding returns. With Purchasing: assets created from a purchase. With
Books: depreciation. With Payroll: deductions on leaving (where the law allows).

### 6.4 Seeing the business

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

**Added after review: Home as a personal command centre.**
- **Widget system:** each module registers widgets (with sizes and what permission they need);
  people add, remove, drag and resize them; layouts saved per person; presets and roles give
  sensible starting layouts; owners can push a layout to a role.
- **Quick actions bar** at the top that changes with role and context: *open drawer* in the
  morning for a cashier, *clock in* when not clocked in, *approve 3 requests* when some are
  waiting, *record expense*, *close drawer* in the evening.
- **The assistant on Home:** a greeting with "3 things to know today" (computed from the
  modules the person can see, with links), and an always-available ask box (§9).
- **"What else can you do?"**: suggestions from the marketplace based on what the business
  does (sells on credit often → CRM reminders; many pay-outs for milk → Inventory recipes).

#### 1D.2 Reports (`/app/reports`)

**Today.** An HR-shaped overview (headcount, attendance rate, lateness, leave, overdue tasks)
with weekly/monthly emails and signals. Shop reports live in Sales and Books.

**Build.** One Reports area with sections: Sales (takings by day/branch/cashier/hour, best
sellers, margin), Money (P&L in plain words, cash flow, dues ageing, supplier dues), Stock
(value, slow movers, wastage), People (existing), Work (project time and profitability);
comparisons (this week vs last); export to Excel; every report schedulable by email.

**Added after review.**
1. **Saved reports:** filters, columns and groupings saved with a name ("My Friday
   comparison").
2. **Shared reports:** shared with a manager, who sees only what their access allows (the same
   report definition, evaluated with their permissions).
3. **Report builder** for S4/S5 (advanced interface mode): pick dimensions, measures, filters
   and chart type, like a small BI tool, over a governed data model (no raw SQL).
4. **Goals:** "৳50,000 this month" with progress on Home and Reports, per branch or person,
   with the assistant noting when you're behind.

#### 1D.3 Ask (AI), 1D.4 Automations, 1D.5 Notifications

- **Ask:** now its own track (§9).
- **Automations:** new triggers (drawer difference over ৳X, pay-out over a limit, dues 30
  days overdue, stock expiring, claim waiting 3 days, licence expiring) and steps (send a
  WhatsApp/SMS later, create a purchase order draft).
- **Notifications:** per-person settings by kind and channel; quiet hours; digest frequency;
  owner defaults per business type.

---

### 6.5 Running the workspace

#### 1E.1 Team (`/app/team`)

**Today.** Members, invites, staff accounts without email, join links with QR, roles
(built-in and custom), password resets for staff, removal. One role and one department
scope per member.

**Build.** The permission builder from §8; bulk invite from the people list; templates
per business type; "copy access from"; "view as"; offboarding checklist (revoke access,
return assets, final settlement, archive).

#### 1E.2 Settings → Business setup

**Today.** Tabs: modules, branches, plan, AI, audit (plus developers, security, data and
platform where allowed). The plan tab shows the plan and limits but can't change them.

**Build.** Foundations §5.2. Every hard-coded default from the Phase 0 audit gets a home.

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

**Added after review.**
- **Mobile-first, obsessively:** the whole sign-up and first day designed and tested on a
  360 px phone in Bangla first, then scaled up; no step needs a laptop. Target: Rahim sells his
  first cup within five minutes of opening the site.
- **"What else can you do?"** after the first-day flow: the marketplace as an app-store-style
  screen with one-tap enable, not buried in Settings.
- **Demo mode without signing up:** a sample business per preset that anyone can open from the
  public site and tap around in, read-only (or resettable every hour), clearly marked as a
  demo, never mixed with real tenants (a dedicated demo workspace per preset, rebuilt nightly).

#### 1E.5 Help and the public site

Every screen links to its help article; articles cover the new scenarios; the public site's
claims are re-checked against what's built after each group of modules.


---

## 7. Phase 2 — One business across its whole life

### 7.1 The aim

Phase 1 makes each module excellent. Phase 2 follows businesses through their real lives
— growing, shrinking, changing shape, having seasons, and closing — and makes the modules
work together at every point. The output is a product that fits a business at every stage
without a migration, a consultant, or lost history.

### 7.2 For each stage or life event, the deliverables

1. **Journey script**: a day, a week and a month-end (or the event itself), step by step with
   screens and data.
2. **Module map**: which modules are on, and the connections between them (§1.5).
3. **Configuration**: what the owner sets up, in order, in Business setup.
4. **Access**: the people and what each may do (§8).
5. **Transitions**: the trigger, what the product suggests, what changes, what the owner
   chooses, and what happens to existing data.
6. **The assistant's role**: what the owner would ask at this stage and get answered (§9).
7. **Scenario test** (API) and **browser walkthrough** for the whole journey.
8. **Gaps** into the register, fixed in the stage's build list.

### 7.3 Growth stages

| Stage | Example | People | Branches | What changes |
|---|---|---|---|---|
| **S0 Solo stall** | Rahim's tea stall | owner + 2 helpers | 1 | cash, credit to regulars, daily bazar, daily wages from the till |
| **S1 Small shop** | a grocery with stock | 5–10 | 1 | stock, suppliers, monthly salaries, a cashier who isn't the owner |
| **S2 Two locations** | second outlet | 10–25 | 2–3 | branch managers, transfers, per-branch P&L, shared customers |
| **S3 Office / agency** | 30-person agency | 20–60 | 1–2 | leave, payroll, projects, documents, approvals, an accountant |
| **S4 Multi-branch company** | retailer or factory | 100–500 | 5–30 | regions, HR team, approval chains, rosters, budgets, audits |
| **S5 Group** | group of companies | 500–5,000 | many | several legal entities, consolidated reports, SSO/SCIM, API, strict access |

These are not a ladder every business climbs: a factory starts at S4 with no till; a tea
stall may add HR and payroll without ever adding stock. The stages are lenses for testing
combinations, not a path the product forces.

### 7.3a Stage by stage: first sketches

These are starting points for each stage's journey script (§7.2 step 1); Phase 2 turns each
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
  shared customers across branches; branch managers' access scoped to their branch (§8.1).
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
- **Modules.** All, plus group layer (§7.7), developer platform, audit exports.
- **Connections.** Inter-company transactions mirrored in both companies' books; group roles
  (CFO sees all books, nothing else); SCIM groups → access templates.
- **Configure.** Group, companies, group roles, SSO, SCIM, API keys, retention policies.


### 7.4 Other life events (added after review)

#### E1 — A seasonal business

**Example.** Shirin runs a clothing stall that triples for Eid-ul-Fitr: a pop-up second stall
for three weeks, 6 temporary sellers, a large stock bought on credit, then back to one stall
and 2 people.

**Needs.** Temporary branches with start and end dates (archived automatically, history
kept); temporary staff with contract end dates (access ends by itself, final pay generated);
seasonal stock and price lists; a season report ("Eid 2026: sales, profit, what's left");
leftover stock marked down or returned to suppliers; next year's season copied from this one.

**Modules.** Point of Sale, Inventory, Purchasing, Payroll (daily/weekly), People, Books,
Reports; Access with time-bound grants.

#### E2 — A pivot

**Example.** Rahim's tea stall becomes a small restaurant: a kitchen, a menu with recipes,
table service, 6 staff.

**Needs.** Change the preset (shows a diff: adds modules and defaults, removes nothing);
items and history kept; new categories and recipes; reports compare before and after the
pivot; the assistant knows the business changed ("since March you're a restaurant").

#### E3 — Downsizing (the inverse of growth)

**Example.** Nasrin's grocery loses money for a year: closes one of two branches, lets 6 of 18
people go, drops payroll to quarterly bonuses only, stops Inventory and keeps a simple till.

**Needs.**
- **Branch closure:** stock transferred or written off, drawers closed, customers' dues moved
  to the remaining branch, staff transferred or settled, the branch archived (reports for its
  history still work).
- **Layoffs:** final settlements in bulk with the legal notice period and compensation
  (retrenchment rules under the Labour Act), access removed on the last day, documents
  (termination letters, experience certificates) from templates.
- **Dropping modules:** read-only history, still in reports and the assistant for past
  periods, re-enabling picks up where it left off; stock frozen at its last count with value
  kept in the books.
- **Plan downgrade:** effective from next month (owner's rule); nothing deleted; over-limit
  modules read-only.
- **Insight before it's too late:** signals for falling margin, rising costs, cash running low
  (Reports and the assistant), so downsizing is a choice, not a surprise.

#### E4 — Closing the business

**Needs.** A guided **close-down**: final pay and settlements for everyone; final supplier
payments and customer collections (or write-offs); stock sold off or written off; the books
closed with a final balance sheet; statutory registers and tax records exported for the years
the law requires them kept; a complete portable export (§10.3); the plan cancelled; the
workspace kept read-only for a retention period, then deleted with the existing 30-day
restore and deletion certificate.

### 7.5 The growth path, plan changes and billing rules

- **Plan changes in the app.** Until billing exists: pilots get plans through an **operator
  invitation** (a link that grants a plan until a date, free). After billing: self-serve.
- **Owner's billing rule:** any change (plan, preset, modules) takes effect immediately for
  use, but the current month is billed on the old plan and the new plan from the next month.
- **Owners only** may change plan, preset and modules; a business can have several owners
  (supported today).
- **Suggestions, not walls:** "14 of 15 people" a week before; "second branch — branch
  managers can now see only their branch".

### 7.6 The connections that make it one product

```
           ┌──────── Point of Sale ─────────┐
   CRM ◀─ credit, payments ─▶ Drawer ◀─ pay-outs, cash-in, drawings, wages
     │                         │
     ▼                         ▼
 Dues ageing             Expenses ◀─ claims ◀─ People ─▶ Assets
     │                         │        ▲
     ▼                         ▼        │ approvals (Access)
   Books ◀────── every money movement ──┤
     ▲                         ▲        │
 Inventory ◀─ receiving ─ Purchasing     │
     ▲                                  │
 Payroll ◀─ attendance, overtime, leave, advances, claims
     │
     └─▶ paid from bank / drawer / wallet ─▶ Books
 Projects ◀─ time, expenses, invoices (CRM) ─▶ project profitability
 Home / Reports / Assistant ◀─ everything, through capabilities and permissions
```

Each arrow gets: the event or call that carries it, what the person sees on both ends (links
in both directions), how a mistake on one end is corrected on the other (reversal, not
delete), what happens when either module is off (standalone mode), and a scenario test.

### 7.7 Groups of companies (moved into Phase 2 core)

The owner wants this as soon as possible. Design:

- A **group** above workspaces: one login, a shared people directory (optional), group
  owners and group roles (a CFO who sees every company's books and nothing else).
- Each company keeps its own books, payroll, tax numbers and currency; nothing mixes by
  accident (row-level security per company stays the foundation).
- **Consolidated reports**: P&L, balance sheet and headcount across companies, with
  currency translation (§10.4) and eliminations of inter-company transactions.
- **Inter-company transactions**: a sale from company A to B mirrored as a purchase in B,
  linked, both sides reversible together.
- **Shared services**: group-level suppliers and customers (optional), group SSO and SCIM,
  group-level audit export.
- **Engineering:** a `groups` layer with memberships; cross-company queries only through
  group-scoped, read-only functions (the same pattern as today's cross-tenant aggregates), never
  by turning row-level security off. Builds on the access engine (§8) and multi-currency.

---

## 8. Phase 2 — Access you can shape person by person

(The engine is built in Foundations §5.3; the screens and the full model land here.)

### 8.1 The model: like Discord, personal settings beat the role

**Effective access = the person's roles, then their personal overrides on top, within scopes,
under limits and conditions.**

1. **Several roles per person** (owner's decision), combined Discord-style. Karim can be
   *Cashier* **and** *Stock keeper*; he gets everything either role allows.
   - **Each role assignment can carry its own scope**: Rina is *Manager* at Banani and
     *Cashier* at Gulshan; she approves refunds at Banani but only sells at Gulshan.
   - **Roles add up; they never take away.** Only a personal *deny* (point 2) removes
     something a role grants, so giving someone an extra role can't silently reduce their access.
   - **Limits from several roles**: the highest applies (a role allowing refunds up to ৳2,000 and
     another up to ৳5,000 gives ৳5,000), unless a personal limit is set.
   - **Shown clearly**: the member's page lists their roles with each role's scope, and every
     permission says which role (or personal setting) it comes from.
   - **Templates combine**: "Cashier + Stock keeper" can be saved as a quick preset for inviting.
   - **Owner is a role too**: a business can have several owners (supported today); "owner" can
     be combined with nothing else because it already includes everything.
2. **Personal overrides beat roles.** For any permission, a person can be set to *allow*,
   *deny* or *inherit* (from roles). Order of evaluation:
   1. Owners have everything (the last owner can't be removed).
   2. A personal **deny** wins over everything else.
   3. A personal **allow** wins over the roles.
   4. Otherwise the roles decide (any role that allows → allowed).
   The member's access page shows each permission with where it came from ("allowed by
   *Cashier*", "denied for Karim personally").
3. **Role templates per preset**: "Shop manager", "Head cashier", "HR officer", "Auditor"
   (read-only, time-limited).
4. **Scopes per permission**: *everything* · *these branches* · *these departments (and
   below)* · *their own team* (reports-to) · *only their own records*.
5. **Limits**: approve expenses up to ৳10,000; refunds up to ৳2,000; discounts up to 10%;
   voids within 10 minutes; pay-outs up to ৳1,000 per shift. Above a limit the action becomes
   an approval request, not a refusal.
6. **Conditions** — this is what decision 10 in v1 meant, in plain words. Optional rules on
   *when and where* someone may use a permission, on top of *what*:
   - **time of day**: Karim may sell only between 6 a.m. and 11 p.m. (outside it the till
     won't open for him);
   - **device**: cashiers may sell only on a registered till, not from their own phone;
   - **network**: the accountant may open the books only from the office network (the
     workspace-wide allowlist exists today; this makes it per person).
   Useful for shops worried about after-hours sales or staff using the app at home. The owner
   decides whether to build these (§14.2).
7. **Field visibility**: salaries, national IDs, cost prices and margins, customers' phone
   numbers, bank details — hideable even when the record is visible.
8. **Time-bound access and delegation**: "acting manager 10–20 Oct"; approvals delegated
   while someone is on leave.
9. **Segregation of duties** warnings (create a supplier and pay it; prepare and approve
   payroll), acceptable with a reason, audited.
10. **Plain-language levels per module**: *No access · See · Use · Manage · Approve*, with an
    "advanced" view of individual permissions.

### 8.2 The screens

- **Add a member**: how they sign in → roles (one or more) → per-module levels, scopes,
  limits, hidden fields, conditions → **preview "what Karim will see"** → invite.
- **Member's access page**: effective access with sources, history of changes, copy from
  another person, compare two people.
- **Bulk changes**, **view as** (read-only, audited), and **access reviews** for S4/S5
  (quarterly "confirm each person still needs this" for managers).

### 8.3 Engineering notes

- An evaluator `can(ctx, permission, resource)` replaces `catalog.resolve()` and the single
  `scope_department_id`; services ask about a resource (this sale, this branch, this person).
- Tables: `member_roles` (a person's roles, each with an optional scope), `member_overrides` (permission, allow/deny, scope, limit,
  conditions, valid from/to), `field_policies`, `delegations`.
- Branch scope needs a branch on every relevant record (missing today on customers).
- Existing members migrate unchanged (one role, no overrides behaves exactly as today).
- The isolation sweep and capability parity tests extend to roles, overrides, scopes, limits
  and conditions; the assistant uses the same evaluator (§9).

---

## 9. Phase 2 — The assistant as a primary interface

The owner's direction: owners should mostly talk to the assistant. Today it answers questions
with sources, proposes some writes for confirmation, drafts text and automations, and is off
until a key is set and the workspace opts in. This track makes it the main way to run the
business, without ever weakening access control.

### 9.1 What it must do

- **Answer anything the person may see**, across every module, with exact numbers from
  capabilities (never guessed), formatted answers (tables, small charts, cards) and links to
  the source ("did I make money this month?" → P&L in words with drill-downs).
- **Act on anything the person may do**, through write capabilities: always shown as a
  proposal with exactly what will change, confirmed with one tap; above limits it creates the
  approval request instead.
- **Undo through chat**: "undo that" reverses the last confirmed action where a reversal
  exists (money: a reversal entry; tasks: restore), within a time window.
- **Proactive briefings**: "3 things to know today" on Home; a weekly brief (exists);
  warnings from signals (cash running low, dues overdue).
- **Context across conversations**: remembers the business (from data, not chat) and the
  person's preferences when they allow it; memory is visible and deletable.
- **Voice in Bangla**: speak a question or a sale ("দুইটা চা, একটা সিঙ্গারা") for people who
  read slowly; speech-to-text through the provider port.
- **Any language the person writes in**, answering in the same.

### 9.2 What it must never do

- See or reveal data the person can't (it calls capabilities as them; tested by the
  isolation and parity suites).
- Act without confirmation, or around a limit or approval.
- Follow instructions found inside data (documents, names, notes): tool results stay data
  (exists, threat model in `docs/security/ai.md`).

### 9.3 Making it work in practice

- **Capabilities for every module** as Phase 1 finishes each one (part of the exit criteria).
- **Evaluation sets**: 30+ real questions and actions per persona in both languages with the
  expected answers; run on every change to prompts, models or capabilities.
- **Cost control** (AI is not optional, but it costs per use): included allowance per plan,
  cheaper models for simple questions, caching repeated questions, the business's own key
  (exists), usage visible to owners and operators.
- **Chat as a surface everywhere**: a floating assistant on every screen that knows which
  screen and record you're on ("explain this payslip").

---

## 10. Cross-cutting tracks

These run alongside Phase 1 and 2, each with its own owner review.

### 10.1 Data migration and cut-over

- **Importers for every module** (Excel/CSV templates in both languages, preview with row
  errors, all-or-nothing): items with prices and variants; customers with opening dues;
  suppliers with opening dues; opening stock with cost per place; an opening trial balance;
  leave balances (exists); salaries and advance balances; assets.
- **A go-live date per business**: everything before it is an opening balance; reports start
  there; the assistant knows.
- **Cut-over checklist per preset/stage** in Business setup.
- **Parallel run**: a period where the business keeps its old method too; side-by-side
  reports to compare (daily takings, stock, payroll totals) before switching off the old way.
- Later: importers from common tools (Tally exports, other POS exports).

### 10.2 Audit trail and compliance

- **Immutability**: posted financial records (sales, journal entries, payroll runs, stock
  movements) can't be edited or deleted, only reversed; enforced in the database.
- **Change history** with before/after on sensitive fields: salaries, bank details,
  permissions, prices, tax settings, branch locations.
- **Auditor access and exports** (§6 Books): a time-limited read-only role; the journal, audit
  log (hash-chained today) and statutory registers in portable formats.
- **Bangladesh labour law**: statutory registers and rules (§6 Payroll), notice periods and
  retrenchment, maternity, minimum wages by sector — checked by a labour lawyer.
- **VAT**: tax-return templates exist; whether receipts and invoices meet Mushak
  requirements is a question for a VAT consultant before claiming it.
- **Data protection** (PDPO 2025): retention schedules per data type, consent records,
  data-subject requests (exists in part).
- **Digital commerce rules** only if online selling is added later.

### 10.3 Backups, disaster recovery and data portability

- **Today:** Neon point-in-time restore; nightly encrypted dumps to R2 for 30 days; restore
  runbook drilled locally; owners export a workspace as a ZIP and restore it into a new one;
  deletion with a 30-day undo and a signed certificate.
- **Add:** targets written down (recovery point ≤ 5 minutes via point-in-time restore;
  recovery time ≤ 4 hours); a tested **single-business restore** from a backup; quarterly
  drills on production; **portable exports** per module in CSV/Excel with a documented format
  (not only our ZIP); **scheduled exports** to the business's own storage (Google Drive,
  S3) for S4/S5; a status page.

### 10.4 Multi-currency

- Base currency per business; **currency per branch** (branches abroad); **transaction
  currency** on sales, invoices, purchases, bills and expenses with the exchange rate at that
  date; rates entered by hand or fetched daily; journal lines store both amounts; month-end
  **revaluation** of open foreign balances; **reporting currency** for groups (§7.7); rounding
  rules per currency (some have no minor unit).
- Money stays integer minor units per currency (today's rule), with the currency always beside
  the amount.

### 10.5 API and developer platform

**Already built** (M10): the `/v1` REST API with a versioned contract and breaking-change
check; API keys with chosen permissions, rate limits, network ranges, expiry, rotation and
usage logs; signed webhooks with a catalogue, retries, delivery log and resend; idempotency
keys; TypeScript and Python SDKs; OIDC sign-in; SCIM; sandbox workspaces; a developer guide
and `/developers` page.

**To extend:** keys scoped by branch and module through the new access engine; API coverage
and webhook events for every new module; a **changes feed** ("everything changed since
cursor X") and bulk export endpoints for BI tools; published SDKs (npm, PyPI); OAuth apps
for third-party integrations (later); developer portal pages per module.

### 10.6 Performance and observability

- **Promises (SLOs)**: 99.5% availability at launch, aiming for 99.9%; the §2.3 budgets.
- **Monitoring**: request latency and errors per endpoint and per tenant, job queues, outbox
  backlog and dead letters, database load; alerts to the owner's phone; error tracking
  (Sentry); uptime checks.
- **Fairness between tenants**: per-tenant rate limits, statement timeouts, background jobs
  that can't starve others, report row limits; the largest tenants can move to their own
  database (S5) without code changes.
- **Slow-query log** reviewed monthly; indexes from the Phase 0 audit.

### 10.7 Feature flags and staged rollout

Flags per workspace, per person and by percentage, managed by platform operators; kill
switches for risky features; every new module ships to pilots first; experiments (e.g. a new
Home layout) measured only with anonymous usage counts; Cloud Run revisions with traffic
splitting for canary releases; database changes in expand-then-contract steps so any revision
can roll back.

### 10.8 WhatsApp and SMS

- **WhatsApp Business Platform** (Meta's Cloud API, or through a provider): needs a verified
  business and a phone number; messages a business starts must use **pre-approved
  templates**; free-form replies only within a 24-hour window after the person writes; priced
  per message by category (utility, authentication, marketing) and country — check current
  rates before deciding who pays.
- **Templates we'd need** (both languages): payslip ready, dues reminder with amount, receipt,
  sign-in code, leave decision, shift reminder, approval request.
- **Opt-in** recorded per person/customer; stop words honoured.
- **SMS fallback** through a Bangladeshi gateway (branded sender names need registration) for
  people without WhatsApp.
- **Cost model**: included messages per plan, then credits — a decision (§14.2).

### 10.9 Private integrations for one company (bKash, banks)

How to integrate a payment provider or bank **for one client first** without making it a
platform-wide feature, and without blocking the SaaS:

- **A provider port**, like the AI provider port: `PaymentProvider` (charge, refund, status,
  webhook), `PayoutProvider` (bulk salary payments). Each integration is an adapter in
  `api/app/integrations/<provider>/`.
- **Per-business integration settings**: credentials stored encrypted with the existing field
  encryption; enabled for that business only by a platform operator through a feature flag.
- **The client's own merchant or bank account.** The money flows to *their* bKash merchant
  account or *their* bank; you are the technology provider. This is usually the realistic
  route in Bangladesh: the client applies for the merchant account (trade licence, bank
  account), the provider gives sandbox and production credentials, and you build against
  them. Agree in writing what you're responsible for.
- **Aggregators** (e.g. SSLCommerz) offer bKash, Nagad and cards through one integration with
  simpler onboarding; often the fastest first step.
- **Banks**: corporate salary payments are usually **files** uploaded to the bank's corporate
  portal (BEFTN formats) rather than live APIs; generating the right file per bank is the
  practical first integration. Host-to-host links come later and need the bank's IT team.
- **Inbound webhooks** per business with signature checks (the webhook verification
  pattern exists for our outgoing webhooks; mirror it).
- **Graduating to the platform**: when a second client wants it, the adapter becomes a
  marketplace connector with self-serve setup.

---

## 11. Phase 3 — Go live and get paid

1. **Deploy** (handbook chapter 10) on the cheapest schedule, with monitoring (§10.6).
2. **Pilots**: any business that will use it (owner's decision), invited free through
   operator invitation links; weekly check-ins; their findings go to the top of the gap
   register.
3. **Billing (M5)**: international cards (Paddle or similar) and a Bangladeshi gateway for
   BDT (trade licence and merchant account needed); the billing rules in §7.5; invoices with
   VAT if registered; per-module or per-plan pricing decided in §14.2.
4. **Legal and compliance**: lawyer's review of terms, privacy and DPA; tax adviser and labour
   lawyer on payroll tables and registers; VAT consultant on receipts and invoices.
5. **Support**: WhatsApp support number, in-app help, status page.
6. **Security before real data**: ZAP scan, penetration test, restore drill on production.

## 12. Phase 4 — Scale and reach

1. **Mobile**: installable app with offline for the till, kiosk and attendance; push
   notifications; native wrappers only if needed (Bluetooth printers, NFC).
2. **Live payments and messaging** from §10.8–10.9 as connectors.
3. **Integrations**: bank statements, accounting exports, e-commerce orders into Sales.
4. **Performance at size**: stored daily totals, partitioning, files on R2, dedicated
   databases for the largest tenants; load tests at 5,000 people and a million sales.
5. **Preset marketplace**: shareable presets (pharmacy, restaurant with recipes, garment
   factory).
6. **More languages** (§2.5).

---

## 13. Honest estimates and checkpoints

### 13.1 Why the v1 estimates were wrong

v1 sized this plan at roughly 70–110 days. The owner is right that this was optimistic: it
assumed skeleton depth per item, and it left out the standards (errors, accessibility,
performance, printing), the marketplace, migration, compliance and everything the review
added. Below, each item is re-sized for a **finished-product standard** in the same units as
v1: focused developer-days with AI help, including tests, both languages, documentation and
the owner's review loop.

### 13.2 Sizes

| Area | Items | Days |
|---|---|---|
| **Phase 0** | 0.1–0.12 | 6–10 |
| **Foundations** | marketplace and rules 10–15 · Business setup and interface mode 12–18 · access engine with multiple roles and approvals 22–32 · shared standards components (errors, jobs, print, widgets, languages, flags) 15–25 · branding and customization (brand, templates, labels, custom fields) 15–22 | 74–112 |
| **Modules: money** | Point of Sale 25–35 · Sales 8–12 · Expenses 10–15 · CRM 15–25 · Purchasing 10–15 · Inventory 20–30 · Books 20–30 | 108–162 |
| **Modules: people** | People 12–18 · Attendance (with kiosk) 15–25 · Leave 10–15 · Payroll (with compliance) 25–40 | 62–98 |
| **Modules: work** | Projects & Tasks 15–20 · Communication 6–10 · Documents 8–12 · Assets 8–12 | 37–54 |
| **Modules: seeing and running** | Home 12–18 · Reports 15–25 · Automations 8–12 · Notifications 5–8 · Sign-up, demo, help, site 12–18 | 52–81 |
| **Phase 2 journeys** | six stages + four life events, connections, growth and shrink paths | 35–55 |
| **Groups of companies** | §7.7 | 15–25 |
| **Access screens and model** | §8 (beyond the engine) | 10–15 |
| **Assistant track** | §9 | 25–40 |
| **Cross-cutting** | migration 15–25 · compliance 15–25 · backups/portability 6–10 · multi-currency 15–25 · API extension 10–15 · observability 8–12 · WhatsApp/SMS 10–15 · each private integration 10–20 | 89–147 |
| **Phase 3** | deploy, pilots setup, billing, legal follow-ups (calendar time for reviews extra) | 15–25 |
| **Total** | | **≈ 530–825 days** |

### 13.3 What that means in calendar time

At v1's estimating standard, that's two to three years for one developer. In practice the
first build (planned at ~150 days) was written in about six days of AI sessions, but to
skeleton depth. Depth work is limited less by typing code than by: understanding real use,
the owner's reviews, testing on real phones, legal and tax checks, and pilots' feedback.

A realistic expectation, assuming the owner reviews within two days and sessions run most
days: **Phase 0 and Foundations in 4–6 weeks; the money and people modules in 3–4 months;
work, seeing-and-running and Phase 2 in another 3–4 months; with the cross-cutting tracks
alongside — roughly 8–12 months to a finished product ready for paid launch.** Pilots should
start much earlier: after Foundations plus the money modules (about 3 months), on feature
flags, because real use is the best test there is.

To go faster without cutting the standard: run independent modules in parallel AI sessions
(separate worktrees, one module each), keep owner reviews short and frequent, and let pilots
reorder priorities.

### 13.4 Checkpoints (the owner walks each)

| After | Walk |
|---|---|
| Phase 0 | the gap register, configuration audit and screenshots |
| Foundations | enable/disable modules, change preset, set up a business, add five people with different access, "view as" each |
| Money modules | a tea stall's day and a grocery's month on a phone, in Bangla |
| People modules | a month of payroll for a 10-person shop with daily wages, and a statutory register |
| Work and seeing | an agency's week; Home and Reports for each persona; the assistant answering 30 questions |
| Phase 2 | each stage and life event end to end, including closing a business |

**Rules that carry over:** English and Bangla everywhere; logic in services; modules never
import the AI layer; every route declares access; every tenant table has row-level security;
the public site only claims what's built; `scripts/check.sh` before every push; commits as
the owner with no AI co-author lines.

**New rules:** no module is done without its exit criteria (§3.3); modules work standalone
and connected; every connection is visible in both directions; nothing a business would
change stays hard-coded; every number is explainable; new work ships behind a flag.

---

## 14. Decisions: made and still open

### 14.1 Made by the owner (6 October)

| # | Decision |
|---|---|
| 1 | No linear order by business type: everyone adds the modules they want; types are presets |
| 2 | Payment methods recorded now; real bKash/bank integrations may be built privately for one client first (§10.9) |
| 3 | If something can be a module, it's a module; payroll and expenses are separate modules the owner chooses; modules excellent alone and much better together |
| 4 | A marketplace of modules with requires/conflicts rules; base modules always included: Users, Access, Business, Home |
| 5 | Customers becomes **CRM**: customers, transactions, invoices and payments; no lead generation |
| 6 | Expense claims can be reimbursed through payroll or cash (the business chooses) |
| 7 | Preset/plan changes allowed any time by owners (several owners allowed); billed on the old plan for the current month, the new one from next month |
| 8 | Interface mode: make it real |
| 9 | Plan changes before billing: free for pilots through operator invitations; self-serve once billing exists |
| 10 | Access works like Discord: personal overrides beat roles |
| 11 | Groups of companies as soon as possible (Phase 2 core) |
| 12 | Pilots: any business that will use it |
| 13 | A finished product, not an MVP; the assistant is not optional and will become the main interface |
| 14 | A person can hold several roles; roles add up, personal overrides beat them |
| 15 | **Branding** (not "assets") is the name for a business's logo, banner, colours, document templates, labels and fields; it's part of the Business base module (§5.5) |

### 14.2 Still open

Write answers under each.

1. **People as a module.** Make People (HR records) a marketplace module separate from Users
   (who can sign in)? Proposed: yes (§1.2).
2. **Merges and splits** in §1.4: split Purchasing from Inventory; Inventory without Point of
   Sale; Announcements → Communication; Approvals into Access; Reports as a base framework.
   Agree with each?
3. **Access conditions** (§8.1 point 6: time of day, device, network per person): build them?
4. **Pricing**: plan tiers (today) or per-module prices on top of a base plan? Both affect the
   marketplace screen.
5. **The assistant's cost**: included questions per plan (today), or unlimited on paid plans
   with fair use, or the business's own key? Voice costs more than text.
6. **Point of Sale details**: variants before per-branch prices? Owner drawings visible to
   managers?
7. **Kiosk sign-in**: PIN/QR on a shared tablet, workers' own phones with passkeys
   (fingerprint), or both?
8. **Demo mode**: read-only, or editable and reset every hour?
9. **WhatsApp/SMS costs**: included per plan, credits, or passed through?
10. **Multi-currency at launch** or after pilots?
11. **A third language**: which, and when?
12. **Who checks the legal tables** (tax slabs, minimum wages, labour registers, VAT): can you
    arrange an adviser and a lawyer before payroll ships with tax on by default?
13. **Custom domains and white-label**: which plans include them? (Custom fields and branding
    are proposed for every plan.)
14. **The equipment Assets module** (§6, 1C.5: laptops, freezers, motorbikes, who holds them,
    servicing, depreciation) was proposed by me, separate from Branding. Keep it, or drop it?

---

## Appendix A — Known gaps

Verified in the code on 5–6 October unless marked **(verify)**. These seed `docs/gaps.md` in Phase 0.

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
| A25 | Access | Approvals are a separate inbox for two request types, not an engine every module uses | missing feature |
| A26 | Inventory | Requires Sales & POS; a warehouse can't track stock without a till | wrong default |
| A27 | People | Every member gets a People profile automatically, mixing "who signs in" with "HR records" | design question |
| A28 | Platform | No feature flags to ship to pilots first | missing feature |
| A29 | All | No error catalogue; errors are toasts that disappear | confusing UX |
| A30 | Till | Offline sales queue in `localStorage`; no visible queue to send or discard | bug risk |
| A31 | Platform | Outbox events that fail 8 times stay undelivered with no dead-letter view or alert | missing feature |
| A32 | Money | Single currency per business; no transaction currency or exchange rates | missing feature |
| A33 | Payroll | Salary tax off by default; no statutory registers, minimum-wage or overtime-cap checks | missing feature |
| A34 | Sign-up | No demo mode; trying the product requires signing up | missing feature |
| A35 | Books | Posted entries are reversed, not edited, by convention in the services; the database does not enforce it (journal tables are ordinary tenant tables, not append-only) | compliance risk |
| A36 | Home | No widgets, quick actions or layout per person | missing feature |
| A37 | Business | No branding (logo, banner, brand colour), document templates, numbering series, custom labels or custom fields | missing feature |
| A38 | Access | One role per member | missing feature |

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
| **Shirin**, owner | seasonal clothing stall, Eid pop-ups | phone | Bangla | temporary branch and staff, big stock on credit, season report |
| **Jahanara**, sewing operator | garment factory, 800 workers | none; kiosk at the gate | Bangla, low literacy | clocks in with a card or PIN; payslip read aloud by the assistant |
| **Mr. Haque**, external auditor | audits Mr. Chowdhury's group | laptop | English | time-limited read-only access; journal and registers export |

