# Progress

Current milestone: **M1, demoable slice** (see `IMPLEMENTATION_PLAN.md` §9).

## M1 checklist

- [x] Plan approved, repo created, pricing set from competitors
- [ ] Repo scaffold, check script
- [ ] API foundation: settings, DB, migrations, RLS roles and policies, tenant context, errors, test harness
- [ ] Auth: sign-up with workspace, email verification, login, refresh rotation, sessions, password reset, TOTP MFA, step-up, rate limiting
- [ ] Workspace core: permissions, roles, members, invites, staff accounts without email, branches, plans and module switches, audit log with hash chain
- [ ] People: employees, departments tree
- [ ] Attendance: clock in/out, overnight shifts, corrections with approval, timesheet, CSV export
- [ ] Web app: shell, auth, onboarding, dashboard, people, attendance, members, settings, security page, English + Bangla
- [ ] Marketing site: landing, pricing, terms, privacy
- [ ] CI workflow, Dockerfile, infra, deploy runbook
- [ ] Playwright e2e + axe
- [ ] Deploy (needs owner: Google Cloud, Neon, Cloudflare accounts)

## Blocked on the owner

- Push the `legacy-nsu-327` tag in the legacy repo (command in the plan, §11 Q1).
- Cloud accounts for deployment (§11 Q10).

## Log

- 2026-09-30: Plan approved. Repo `omikhan4901/companymgmt` created by the owner.
