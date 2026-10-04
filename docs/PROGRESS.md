# Progress

Current work: **the owner's 2026-10-04 plan** (below): the marketing site in the ResumeX
style, then M6 → M7 → M8 → M9 → M10 → M11, then a legal review. M5 (Paddle billing) is
on hold. Going live still waits on the owner's cloud accounts (`runbooks/deploy.md`).

## Owner decisions, 2026-10-04 (follow these)

Work order: **marketing site → M6 → M7 → M8 → M9 → M10 → M11 → legal review.** No
spending, no Paddle work (M5 on hold). Build and test everything that needs no owner
input; list what does under "Blocked on the owner".

- **Marketing site:** restyle the public site (`web/src/app/(site)`) in the ResumeX look
  the owner uses elsewhere: teal `#007b7b` (dark `#006262`, tints `#effafa` / `#d5f2f1` /
  `#a9e3e1`), ink `#0f1f2a`, navy `#002a3a`, Inter for text and Plus Jakarta Sans for
  headings, a faint teal grid behind the hero, 10 px rounded buttons with a soft teal
  shadow, slate greys. The product (`/app`) keeps Atlas. Public pages only claim what's
  built; it's marketing only, no sign-up changes.
- **M6 AI:** Gemini Flash. No key is configured: the code must switch AI on by itself the
  moment `GEMINI_API_KEY` is set (and stay cleanly off, with a clear message, without it).
  The provider sits behind a port so others can be added. AI allowances per plan are
  ours to configure (an operator-only setting, not hard-coded); every change notifies
  each workspace's owners and admins. Starting values are ours to choose.
- **M7 AI everywhere:** AI help across almost every module. Each workspace's admins tick
  which features get AI (all off until they choose). The AI proposes, a person confirms.
- **M8 Shop pack:** receipts by browser printing for now (Bluetooth/USB printers later).
  Tax is fully configurable by each workspace (rates, names, inclusive or exclusive,
  per product, compound where needed) so any country works; no country's rules are
  guessed or built in. Cash payments only for now. Dues ("baki khata") and expenses.
- **M9 Inventory and accounting:** double-entry books. VAT returns and tax filings are
  customisable report templates the workspace's own accountants set up (which accounts
  and tax codes go in which box), not built-in rules for any one country.
- **M10 Enterprise:** build and test everything that needs no owner intervention (SSO,
  SCIM, API keys, bring-your-own AI key, dedicated-database support); real identity
  providers and paid infrastructure wait for the owner.
- **M11:** make it as secure as possible. The owner arranges the penetration test.
- **Easy onboarding and addresses (asked 2026-10-04, build with M10):** each workspace gets
  its own address `<slug>.companymgmt.app` at sign-up (wildcard DNS; reserved and
  lookalike names refused; cookies stay per subdomain), showing its name and logo and
  signing staff in without a workspace code. Plus invite links and QR codes, a WhatsApp
  share, optional sample data to try and delete, and an owner's first-day checklist.
  Customers' own domains (`hr.theircompany.com`) through Cloudflare for SaaS custom
  hostnames as a paid-plan feature once billing exists. The wildcard DNS record needs
  the owner's domain.
- **After M11:** a thorough legal review: terms, privacy, data processing, AI use,
  cross-border transfer, looking at what comparable companies publish. For a lawyer to
  check, not legal advice.

## M1 checklist

- [x] Plan approved, repo created, pricing set from competitors
- [x] Repo scaffold, check script (`scripts/check.sh` runs everything CI runs)
- [x] API foundation: settings, DB, migrations, RLS roles and policies, tenant context, errors, test harness
- [x] Auth: sign-up with workspace, email verification, login, refresh rotation with reuse detection, sessions, password reset, TOTP MFA + recovery codes, step-up, rate limiting, Turnstile hook
- [x] Workspace core: permissions, built-in and custom roles, members, invites, staff accounts without email, branches, plans and module switches, hash-chained audit log
- [x] People: employees (encrypted national ID), department tree, manager scope
- [x] Attendance: clock in/out, overnight shifts, time zones, corrections with approval, forgot-to-clock-out flow, timesheet, CSV export
- [x] Web app: shell, auth pages, onboarding wizard, home, attendance, people, team, settings, account (2-step, devices), English + Bangla
- [x] Marketing site: landing, pricing, terms, privacy (drafts, legal review pending)
- [x] Playwright e2e + axe (desktop and phone), WCAG AA fixes
- [x] CI (checks, e2e, security scans, CodeQL, infra validate), Dockerfile, OpenTofu for GCP, deploy workflow, runbooks
- [ ] Deploy (needs owner: Google Cloud, Neon, Cloudflare, email; about an hour following `runbooks/deploy.md`)
- [ ] After deploy: k6 baseline load test, measure idle cost, first restore drill

## Numbers (for the marketing kit; measured, not estimated)

- API tests: 105 passing, 89.9% line+branch coverage (gate 85%).
- Tenant isolation: every route with an id (auto-discovered) is called with another workspace's ids; all tenant tables checked for forced RLS.
- Browser tests: 3 journeys × 2 devices, axe WCAG 2.2 AA on 14 page checks, English and Bangla.
- API image: 350 MB, non-root.

## Blocked on the owner

- Push the `legacy-nsu-327` tag in the legacy repo (command in the plan, §11 Q1).
- Cloud accounts for deployment (runbook).
- Legal review of the privacy policy and terms (plan Q7).
- Check the Bangladesh salary tax table (Payroll → Settings) against the Finance
  Ordinance 2025 with a tax adviser before turning tax deduction on.

## Decisions made while building

- People is always on (not counted as a module): every other module needs it.
- Every member gets a People profile automatically (so they can clock in); it counts
  towards the plan's people limit.
- Scoped roles without a department set see the whole workspace; the UI asks for a
  department when inviting managers.
- A shift open for more than 24 hours can't be clocked out; the person asks for a fix,
  the shift is set aside (not counted) until approved, and they can clock in again.
- Internal endpoints use a shared-secret header (from Secret Manager) rather than OIDC,
  to keep the free tier simple; revisit if Cloud Tasks is added.
- Base images come from `mirror.gcr.io` (avoids Docker Hub rate limits).

## M1.5 marketing kit: done

README with real screenshots (demo data from `api/scripts/demo_seed.py`), and in
`docs/marketing/`: demo video script, case study, resume bullets, LinkedIn post,
architecture one-pager. Only built features and measured numbers.

## M1.6: done (new design, Next.js, location-based attendance)

- **Location check** on clock-in: branch geofences, workspace setting off / record /
  required (default), clock-out never blocked, positions rounded to about 11 m and saved
  only at clock events. Owners place branches with the device location.
- **Atlas design**: white default, dark mode, four accents (Plum, Saffron, Garnet, Ink),
  chosen per device and applied before first paint.
- **One Next.js app** (`web/`) replaces the Vite SPA and the Astro site: static export,
  per-page Content Security Policy with script hashes, Radix + Tailwind components.
- **Same-origin API**: a Cloudflare Pages Function serves `/v1` on the web address, so the
  refresh cookie is first-party even on `*.pages.dev`; with `PROXY_TOKEN` set the API
  refuses direct `/v1` calls and takes the client IP from Cloudflare (closes an
  X-Forwarded-For spoofing gap in per-IP rate limits).
- Numbers: 119 API tests (90% coverage), 17 web unit tests, 6 browser scenarios × desktop
  and phone against the production build, each page checked with axe (WCAG 2.2 AA), for
  sideways scrolling and for CSP violations.

## M2: done (leave, payroll, data rights)

- **Leave**: types, work week, holidays, balances (joining-date share, monthly accrual,
  carry-over), approvals with no self-approval, team calendar that shows who is away but
  not why, adjustments. Screens in English and Bangla; "Away today" on home.
- **Payroll**: salaries by effective date (monthly, hourly, daily; cash, bank, wallet),
  advances, pay runs draft → review → finalized → paid (four-eyes, recent sign-in to
  finalize), overtime from attendance, unpaid leave, festival bonuses, shortfalls carried
  as advances, transfer sheet, payslip PDFs in English and Bangla with bundled fonts.
  Salary tax is an editable table, off by default.
- **Data rights**: owners export everything (ZIP) and can restore an export into a new
  workspace; everyone downloads their own data; deleting a workspace has a 30-day
  restore window, then a purge job and a signed deletion certificate; audit entries
  follow the plan's retention with anchors that keep the chain verifiable; a workspace
  can require two-step verification for owners and admins.
- **Operations**: nightly maintenance and encrypted backup jobs (pg_dump → age → R2,
  30 days) scheduled by OpenTofu; restore drilled locally.
- Done-when check: leave and payroll edge cases tested (Hypothesis on pay maths); 500
  people run payroll in about a second; Bangla payslips checked for the bundled font and
  text (and looked at); an export restores into an empty workspace (test and browser
  journey).
- Numbers: 168 API tests (92% coverage), 22 web unit tests, 9 browser scenarios × desktop
  and phone with axe, sideways-scroll and CSP checks on every page.

## M3: done (work and knowledge)

- **M3.1 foundations: done.** People and attendance reads moved into services; a
  capability registry (typed reads over people, attendance, leave, payroll and
  notifications, each with its permission and module) listed and invoked under `/v1/ai`,
  with writes refused until propose-and-confirm (M7); a context builder (`/v1/ai/context`);
  an append-only domain event log written in the same transaction as each change, with
  in-transaction and outbox subscribers. A parity test proves every read capability
  answers (and refuses) exactly like its REST route for an owner, a scoped manager and an
  employee.
- **M3.2 notifications: done.** Requests go to the people who can decide them in that
  person's department scope; decisions go back to the person; nobody hears about their
  own actions; payslip notices leave out run totals. Bell with unread count in the header
  (English and Bangla), kept six months, included in "my data". A daily email lists what
  each person hasn't read (once, in their language, an hour's grace, can be turned off on
  the account page; staff without email never get one).
- **M3.3 tasks and projects: done.** Projects with members and a home department; a
  board (to do, doing, done) with drag and drop and a keyboard-friendly move menu;
  tasks with assignee, due date, priority, checklist and comments; "My work" grouped by
  overdue, today, this week and later, also on the home screen. Members work on their
  projects, managers run projects in their departments, and assignment, comments,
  completion and joining a project notify the people involved. Edits made in quick
  succession are queued so none is lost to a version clash.
- **M3.4 announcements: done.** Posts to everyone, some branches, or some departments and
  the teams under them; pinned first; managers post only to their own departments. Read
  receipts ("read by 12 of 30", with who hasn't) for the author and admins; posts count as
  read when shown; the audience is notified; "Latest news" on the home screen.
- **M3.5 documents and policies: done.** Documents for everyone, some roles or some
  departments (the visibility is stored with each document, ready for permission-aware
  search); versions kept in Postgres, up to 10 MB each, checked by their content and
  always downloaded as attachments; policies can ask people to acknowledge each version,
  with an "acknowledged by 12 of 30" report and a "To read" card on home. Files come
  across in workspace exports. Found and fixed on the way: workspace imports over 1 MB
  were refused by the request size limit.
- **M3.6 approvals inbox: done for leave and time fixes.** One inbox lists everything
  waiting on a person's decision, oldest first, using each module's own permission,
  department scope and module switch; decisions go back to the module (same rules, same
  notifications); nobody decides their own requests there. Request notifications open
  it, and "Waiting for you" on home uses it. Multi-step chains (by plan) wait for
  expenses and purchases, which will be the first kinds that need them.
- **M3.7 onboarding checklists: done.** Owners and admins write checklists of items for
  the new joiner or their manager, each due some days after the first day, optionally
  pointing at a document. Starting one (by hand, or by itself for everyone who joins)
  turns it into ordinary tasks, so items show up in My work and in notifications; the
  manager item goes to whoever runs the joiner's department. Acknowledging the document
  ticks its item off. Managers see who is being onboarded and how far along; joiners
  get a "Your first days" card on home. Found on the way: a second `RunOut` model
  mangled the payroll type names in the contract; a test now keeps schema names unique.
- **M3.8 a 30-person agency's week: done.** `api/scripts/agency_week.py` plays a week at
  Nokshi Digital through the real API: an owner, an admin, three managers and their
  teams clock in and out, plan three client projects on boards and get most of the work
  done, read the owner's note, acknowledge the code of conduct, ask for leave and a time
  fix that managers approve from the inbox, and welcome a joiner whose checklist starts
  by itself. The API test checks the outcome (30 of 30 acknowledged and read, nothing
  waiting on anyone, the boards and the joiner's progress) in about 20 seconds; the
  browser test seeds the week, then finishes it in the UI. The per-address sign-in limit
  became a setting (`LOGIN_LIMIT_PER_IP`, default 30 per 5 minutes), raised only for
  browser test runs.
- **M3's "done when" is met:** a 30-person agency runs a week entirely in the product,
  and capability parity with the REST routes is tested. Deferred on purpose: approval
  chains with several steps, which arrive with expenses and purchases.
- Next: M4, the pilot release. Deployment waits on the owner's cloud accounts (see
  "Blocked on the owner"); everything else in M4 is being built meanwhile.

## M4: partly done (pilot release; paused)

- **M4.1 spreadsheet import: done.** Owners and admins bring a company in from a CSV:
  people (matched to existing profiles by code, then email, and updated), departments
  from paths like "Design / Motion", and the days of leave each person has left this
  year (recorded as adjustments, so balances stay explainable). Headers can be English
  or Bangla, dates day-first (Bangla digits too). A preview lists every row's problems
  in plain words before anything is saved; the import is all or nothing and respects
  the plan's people limit. A template lists the workspace's own leave types. Found on
  the way: the template's formula guard (`'+880…`) made phone numbers fail on the way
  back in; leading apostrophes are now read as spreadsheets mean them.
- **M4.2 reports: the dashboard is done.** A Reports page (and the `reports.overview`
  capability) for any period and department: people by department, joiners and leavers,
  attendance rate (present ÷ expected, where expected skips days off, holidays and
  approved leave), late arrivals against a new "working day starts at" setting with a
  grace period, leave taken by type, and open and overdue tasks, with who is late or
  overdue most. Managers see their own departments. Found on the way: a month of day
  labels made the chart wider than a phone; the agency seed counted Saturday as a
  working day.
- **M4.2 report emails: done.** Anyone who can see reports gets the overview every week
  (on the first day of the workspace's week) and/or every month, for a department they
  choose; a daily job works each report out as the subscriber (`member_ctx`), so it only
  shows what they could see, and sends it once, in their language.
- **Hardening before the pause:** people without a joining date now count from when they
  were added (a new workspace no longer looks absent for the whole year); imports treat
  "Design" and "design" as one new department.
- **Paused here at the owner's request (2026-10-01).** Everything above is tested and
  pushed. What's left is listed under "Future work" in the README. `docs/GUIDE.md` is the
  developer guide for picking the code up by hand. Next when work resumes: M4.3 in-app
  help and contact support, then the pilot playbook.

## Log

- 2026-09-30: Plan approved. Repo created. M1 API, web app, site, tests, CI and infra built and pushed. M1.5 marketing kit written. Legacy README points here.
- 2026-09-30: Owner asked for a new design and a Next.js/NestJS stack. Three design directions drawn (`docs/design/directions/`); M2 Leave paused pending the choice.
- 2026-09-30: Atlas chosen (C, white default, four accents). Location-based attendance on the API. Plan rewritten: every milestone explained, AI-ready architecture (§3.7), first market (§2.0), roadmap reordered.
- 2026-10-01: M1.6 done: Next.js app with Atlas themes replaces web/ and site/; location-checked clock-in in the UI; /v1 served through a same-origin Pages Function.
- 2026-10-01: M2 Leave API pushed: Bangladesh defaults near the Labour Act 2006, balances checked again on approval, colleagues see who is away but not why. 135 API tests.
- 2026-10-01: M2 Leave web screens: ask with a live day count, approve, month calendar, balances, settings. Demo seed includes leave.
- 2026-10-01: M2 Payroll pushed: API, pay maths with Hypothesis invariants, 500 people in ~1 s, payslip PDFs (WeasyPrint, bundled Bangla fonts), web screens, browser journey.
- 2026-10-01: M2 done: data rights (exports and import, deletion with a 30-day restore and signed certificate, audit retention with anchors, admin two-step policy), nightly maintenance and encrypted backup jobs.
- 2026-10-01: M3.1 pushed: capability registry, AI context, domain events. M3.2 in-app notifications.
- 2026-10-01: M3.2 notifications done (in-app and daily email digest). CI caught forms wiping typed input when data loaded late; fixed with a browser test.
- 2026-10-01: M3.3 tasks and projects: API, board, task panel, My work, browser journey on desktop and phone.
- 2026-10-01: README remade. M3.4 announcements with read receipts: API, feed, composer, receipts, browser journey.
- 2026-10-01: M3.5 documents and policies with acknowledgements; large workspace imports fixed.
- 2026-10-01: M3.6 approvals inbox for leave and time fixes; time-fix decisions moved into the attendance service.
- 2026-10-01: M3.7 onboarding checklists: templates, runs as tasks, automatic start on joining, document items tick off on acknowledgement.
- 2026-10-01: M3.8 a 30-person agency's week, played through the API and finished in the browser. M3 done.
- 2026-10-01: M4.1 spreadsheet import of people, departments and leave balances, with a preview.
- 2026-10-01: M4.2 reports dashboard and lateness settings.
- 2026-10-01: M4.2 report emails. Edge-case fixes. Developer guide and final README. Paused.
