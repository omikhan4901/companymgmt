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
- UI redesign and stack (asked 2026-09-30): the first UI looked too much like ResumeX.
  Pick a direction in `docs/design/directions/` (A Graphite, B Shift, C Atlas, or A for
  managers + B for staff phones) and confirm the stack: Next.js for web + site (proposed),
  keeping FastAPI (proposed) or rewriting the API in NestJS. M2 is paused until then,
  because both answers change what gets built next.

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

## Next: redesign, then M2

- Rebuild the web app and marketing site in Next.js with the chosen design.

- M2: Leave, Payroll (Bangladesh preset), workspace/personal export and deletion,
  nightly encrypted backups, audit retention, MFA policy for admins.

## Log

- 2026-09-30: Plan approved. Repo created. M1 API, web app, site, tests, CI and infra built and pushed. M1.5 marketing kit written. Legacy README points here.
- 2026-09-30: Owner asked for a new design and a Next.js/NestJS stack. Three design directions drawn (`docs/design/directions/`); M2 Leave paused pending the choice.
