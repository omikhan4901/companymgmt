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

## Next

The roadmap was reordered on 30 Sep 2026 for the first market (20–100 person agencies)
and the AI layer. See `IMPLEMENTATION_PLAN.md` §9: M2 leave, payroll and data rights; M3
work and knowledge with AI-ready foundations; M4 pilots; M5 billing; M6–M7 AI.

- M2 Leave: done. API (types, work week, holidays, balances with joining-date share,
  monthly accrual and carry-over, approvals, team calendar, adjustments) and web screens
  (my leave, requests, calendar, team balances, settings, "Away today" on home), in
  English and Bangla, with a browser journey on desktop and phone.
- M2 then: Payroll (Bangladesh preset), payslip PDFs, workspace/personal export and
  deletion, nightly encrypted backups, audit retention, MFA policy for admins.

## Log

- 2026-09-30: Plan approved. Repo created. M1 API, web app, site, tests, CI and infra built and pushed. M1.5 marketing kit written. Legacy README points here.
- 2026-09-30: Owner asked for a new design and a Next.js/NestJS stack. Three design directions drawn (`docs/design/directions/`); M2 Leave paused pending the choice.
- 2026-09-30: Atlas chosen (C, white default, four accents). Location-based attendance on the API. Plan rewritten: every milestone explained, AI-ready architecture (§3.7), first market (§2.0), roadmap reordered.
- 2026-10-01: M1.6 done: Next.js app with Atlas themes replaces web/ and site/; location-checked clock-in in the UI; /v1 served through a same-origin Pages Function.
- 2026-10-01: M2 Leave API pushed: Bangladesh defaults near the Labour Act 2006, balances checked again on approval, colleagues see who is away but not why. 135 API tests.
- 2026-10-01: M2 Leave web screens: ask with a live day count, approve, month calendar, balances, settings. Demo seed includes leave.
