# Progress

Current milestone: **M1, demoable slice**: code complete; waiting on the owner's cloud
accounts to go live (see `runbooks/deploy.md`).

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

## M3: in progress (work and knowledge)

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
- Next: documents and policies, the
  approvals inbox, onboarding checklists, then a 30-person sample agency week.

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
