# CompanyMgmt

**Attendance and team management for every business, from a tea stall with two staff to a
company with many branches.** Multi-tenant SaaS in English and বাংলা.

![Timesheet](docs/screenshots/timesheet.png)

> **Status:** Milestone 1 of 9 is built and tested. It isn't live yet; deployment is
> scripted and waits on cloud accounts ([deploy runbook](docs/runbooks/deploy.md)).
> Payroll, point of sale, inventory and accounting come next ([roadmap](docs/IMPLEMENTATION_PLAN.md#9-phased-roadmap),
> [progress](docs/PROGRESS.md)).

## What it does today

- **Sign up in two minutes.** Pick your language and business type; the workspace switches
  on only what you need, with a 14-day trial of the Growth plan.
- **Clock in from any phone.** One big button. Overnight shifts count towards the day they
  started, and every branch keeps its own time zone.
- **Fair fixes.** Forgot to clock out? People ask for a correction; a manager approves or
  rejects it; everything is recorded. Nobody can approve their own request.
- **Monthly timesheets** per person per day, with a spreadsheet export that is safe to open
  in Excel (Bangla names intact, formulas neutralised).
- **People and departments.** Profiles, a department tree and branches. Managers see only
  their own part of the tree.
- **Staff without email.** Add a cashier with a username; they sign in with the workspace
  code and must choose their own password on first sign-in.
- **Roles.** Owner, Admin, Manager, Accountant, Cashier, Employee, plus custom roles.
  Nobody can grant a permission they don't hold.
- **Security you can see.** Two-step verification, a list of signed-in devices, and an
  audit log with a built-in integrity check.

| | |
|---|---|
| ![Home](docs/screenshots/home.png) | ![Requests](docs/screenshots/corrections.png) |
| ![People](docs/screenshots/people.png) | ![Plans](docs/screenshots/plans.png) |

<p align="center">
  <img src="docs/screenshots/phone-home-bangla.png" width="260" alt="Staff home screen on a phone, in Bangla" />
  <img src="docs/screenshots/phone-attendance-bangla.png" width="260" alt="Attendance on a phone, in Bangla" />
</p>

## How it's built

```mermaid
flowchart LR
  U[Browser / phone] --> CF[Cloudflare: DNS, TLS, WAF]
  CF --> P[Pages: React app + Astro site]
  CF --> R[Cloud Run: FastAPI, scales to zero]
  R -->|"SET LOCAL app.tenant_id"| DB[(Neon Postgres<br/>row-level security)]
  R --> SM[Secret Manager]
  GH[GitHub Actions] -->|OIDC, no keys| R
```

| Layer | Choice | Why |
|---|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic | Typed, fast to build, generates an OpenAPI contract |
| Data | PostgreSQL 16 with **forced row-level security** on every tenant table | Isolation enforced by the database, not only by code |
| Web app | React 19, TypeScript, Vite, antd 6, Tailwind 4, TanStack Query, i18next | Static files: free to host; typed client generated from the API |
| Site | Astro | Static, fast, no JavaScript needed |
| Hosting | Cloud Run + Neon + Cloudflare Pages | Everything scales to zero: about $1/month with no customers (the domain) |
| Infra | OpenTofu, GitHub OIDC → least-privilege service accounts | Reproducible, no long-lived keys |

A modular monolith: `platform` (accounts, workspaces, roles), `people`, `attendance`, with
module boundaries enforced in CI by import-linter.

### Tenant isolation, three layers

1. **App:** the workspace comes from the signed token, and membership and role are
   reloaded on every request (so a role change applies immediately).
2. **Database:** every tenant table has `FORCE ROW LEVEL SECURITY` with a policy on
   `app.tenant_id`, set per transaction. The API's database role doesn't own the tables
   and can't bypass RLS. With no workspace set, queries return nothing.
3. **References:** composite foreign keys `(tenant_id, id)`, so a row can never point at
   another workspace's row.

A test calls **every API route that takes an id** with another workspace's ids (the routes
are discovered automatically, so new ones are covered) and checks that nothing leaks or
changes.

### Security (OWASP ASVS 5.0 Level 2 target)

Argon2id passwords checked against 100k breached passwords · 10-minute EdDSA access tokens
kept in memory · rotating refresh tokens in an httpOnly, SameSite=Strict cookie, where
reusing an old one ends the session · TOTP two-step verification with recovery codes ·
step-up confirmation for sensitive actions · rate limits with a CAPTCHA after repeated
failures · append-only, hash-chained audit log · AES-256-GCM field encryption bound to
each record · strict security headers and CSP · CSV formula-injection protection. Status
and evidence for each item: [docs/security/asvs-l2.md](docs/security/asvs-l2.md).

### Tests

- **105 API tests**, 90% line and branch coverage (CI gate: 85%), all against a real
  Postgres: auth, isolation, workspaces, people, attendance, plans.
- **Browser journeys** (Playwright) on desktop and phone: sign up → add staff → staff
  signs in in Bangla and clocks in → owner sees the timesheet. **axe WCAG 2.2 AA** checks
  run on every page visited.
- Edge cases (overnight shifts, daylight saving, leap days, double clicks, stale edits,
  Bangla and RTL names, replayed tokens…) are mapped to their tests in
  [docs/testing/edge-cases.md](docs/testing/edge-cases.md).
- CI also runs ruff, mypy `--strict`, ESLint, TypeScript, a migration drift check, an
  API contract check, gitleaks, pip-audit, npm audit, Trivy and CodeQL.

## Run it locally

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22, PostgreSQL 16.

```bash
cp .env.example .env
scripts/dev-db.sh                                   # local roles and databases
cd api && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload                # http://localhost:8000
uv run python -m scripts.demo_seed                  # optional: a demo workspace
cd ../web && npm install && npm run dev             # http://localhost:5173
```

Before pushing, run everything CI runs: `scripts/check.sh` (add `E2E=1` for the browser
tests).

## Project documents

- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): audit of the original university
  project, product scope, architecture, security, testing, billing, costs, roadmap.
- [Progress](docs/PROGRESS.md) · [Deploy runbook](docs/runbooks/deploy.md) ·
  [Restore runbook](docs/runbooks/restore.md)

This started as a group project for CSE327 at North South University (the original is
preserved in [327_Company_Management_System](https://github.com/omikhan4901/327_Company_Management_System)).
CompanyMgmt is a ground-up rewrite as a real product.

## License

Copyright © 2026 Mehboob Ehsan Khan. All rights reserved. The source is public for
portfolio purposes; it is not open-source licensed.
