# Resume bullets

Pick 3–4. Every number is measured (see `docs/PROGRESS.md`). Don't claim users, uptime or
revenue until they exist.

**CompanyMgmt**: multi-tenant attendance and HR SaaS (FastAPI, PostgreSQL, React/TypeScript) · 2026

- Rebuilt a university group project into a multi-tenant SaaS, replacing unsalted SHA-256
  passwords and in-memory sessions with Argon2id, rotating refresh tokens with reuse
  detection, and TOTP two-factor authentication.
- Enforced tenant isolation in PostgreSQL with forced row-level security and composite
  foreign keys, verified by a test that calls every ID-based API route with another
  tenant's IDs.
- Wrote 105 API tests (90% line and branch coverage) and Playwright end-to-end tests on
  desktop and mobile with automated WCAG 2.2 AA checks, gated in GitHub Actions CI.
- Built a bilingual (English/Bangla) React app for attendance, timesheets, correction
  approvals and role-based access, including staff accounts that need no email.
- Designed serverless infrastructure (Cloud Run, Neon, Cloudflare) as OpenTofu code with
  GitHub OIDC deploys, scaling to zero so idle hosting costs nothing.
- Added a hash-chained, append-only audit log with integrity verification, and AES-256-GCM
  encryption for national ID numbers.

**Keywords (ATS):** Python, FastAPI, SQLAlchemy, PostgreSQL, Row-Level Security, React,
TypeScript, Vite, Tailwind CSS, REST API, OpenAPI, JWT, OAuth 2.0 concepts, TOTP/MFA,
OWASP ASVS, Playwright, pytest, CI/CD, GitHub Actions, Docker, Google Cloud Run,
Terraform/OpenTofu, Cloudflare, accessibility (WCAG), internationalization (i18n).
