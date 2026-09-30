# CompanyMgmt

A multi-tenant company management suite that scales from a tea stall with two staff to a
company with thousands of employees across branches: people, attendance, leave, payroll,
point of sale, customers and dues, expenses, inventory, accounting and reports. Each
workspace switches on only the modules it needs.

**Status:** in development (Milestone 1). See [docs/PROGRESS.md](docs/PROGRESS.md) and the
full [implementation plan](docs/IMPLEMENTATION_PLAN.md).

## Stack

- **API**: Python 3.12, FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic, PostgreSQL with
  row-level security for tenant isolation.
- **Web app**: React, TypeScript, Vite, antd, Tailwind CSS.
- **Marketing site**: Astro.
- **Hosting** (planned): Google Cloud Run, Neon Postgres, Cloudflare Pages and R2. Scales to
  zero, so it costs nothing while idle.

## Run it locally

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22, PostgreSQL 16.

```bash
cp .env.example .env          # then fill in the values
scripts/dev-db.sh             # creates the local database and roles
cd api && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd web && npm install && npm run dev
```

Run every check before pushing:

```bash
scripts/check.sh
```

## License

Copyright © 2026 Mehboob Ehsan Khan. All rights reserved. The source is public for
portfolio purposes; it is not open-source licensed.
