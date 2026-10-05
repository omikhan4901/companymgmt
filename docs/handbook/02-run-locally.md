# 2. Run it on your computer

About 20 minutes the first time. You'll end with the API on port 8000, the web app on
port 3000, and a workspace full of demo data.

## 2.1 Install the tools

| Tool | Version | Why | Get it |
|---|---|---|---|
| Git | any recent | the code | <https://git-scm.com/downloads> |
| Python | 3.12 (3.13 works) | the API | <https://www.python.org/downloads/> |
| uv | 0.8 or later | installs Python packages and runs tools (pip + venv, faster) | <https://docs.astral.sh/uv/getting-started/installation/> |
| Node.js | 22 LTS | builds and runs the web app | <https://nodejs.org/> |
| PostgreSQL | 16 | the database | <https://www.postgresql.org/download/> |
| Pango | system library | WeasyPrint draws payslip PDFs with it | Linux `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`; Mac `brew install pango` |

**Windows:** use [WSL 2](https://learn.microsoft.com/windows/wsl/install) (Ubuntu inside
Windows) and install everything inside Ubuntu. The scripts are bash.

**Mac:** `brew install git uv node@22 postgresql@16 pango`, then
`brew services start postgresql@16`.

**Ubuntu/Debian:**

```bash
sudo apt install git postgresql-16 libpango-1.0-0 libpangoft2-1.0-0 curl
curl -LsSf https://astral.sh/uv/install.sh | sh
# Node 22: https://nodejs.org/en/download (the "Linux" tab shows the nvm commands)
```

Check:

```bash
git --version; python3 --version; uv --version; node --version; psql --version
```

## 2.2 Get the code

The repository is private, so clone it with your GitHub login (GitHub Desktop, or `gh
auth login`, or an SSH key):

```bash
git clone https://github.com/omikhan4901/companymgmt.git
cd companymgmt
```

## 2.3 Create the database

The API uses three Postgres roles on purpose (chapter 3.4 explains why):

| Role | Used by | Can |
|---|---|---|
| `cm_owner` | migrations, admin scripts | owns every table |
| `cm_app` | the running API | read and write rows, but **not** bypass row-level security, and doesn't own anything |
| `cm_backup` | the nightly backup | read everything, change nothing |

One script creates the roles and two databases (`companymgmt` for the app,
`companymgmt_test` for the tests). It's safe to run again.

```bash
# Linux: start Postgres first
sudo service postgresql start         # or: sudo systemctl start postgresql
                                      # (in a container: sudo pg_ctlcluster 16 main start)
scripts/dev-db.sh
```

On a Mac there's no `postgres` system user; give the script a superuser connection:

```bash
ADMIN_DATABASE_URL=postgresql://$(whoami)@localhost:5432/postgres scripts/dev-db.sh
```

## 2.4 Settings (`.env`)

```bash
cp .env.example .env
```

The defaults work locally as they are. The API reads `.env` from the repository root
(`api/app/core/config.py`, `env_file=("../.env", ".env")`). Never commit `.env`; it's in
`.gitignore`. Every variable is listed in chapter 13.1; the ones worth changing locally:

| Variable | Local value | Why |
|---|---|---|
| `AI_PROVIDER` | `fake` | try the AI screens without a key (a scripted model) |
| `GEMINI_API_KEY` | your key | try the real assistant (leave `AI_PROVIDER` empty) |
| `LOGIN_LIMIT_PER_IP` | `1000` | the demo scripts sign 30 people in from your computer |
| `SIGNUP_LIMIT_PER_HOUR` | `1000` | create many workspaces while testing |
| `INTERNAL_TOKEN` | any string | lets you call the scheduled jobs by hand (2.8) |
| `PLATFORM_OPERATORS` | your email | see Settings → Platform (needs two-step sign-in on) |

## 2.5 Start the API (terminal 1)

```bash
cd api
uv sync                                  # installs packages into api/.venv (first time: a minute)
uv run alembic upgrade head              # creates or updates the tables
uv run uvicorn app.main:app --reload --port 8000
```

- <http://localhost:8000/docs>: every endpoint, generated from the code, with "Try it out".
  (Only in `ENV=dev` or `test`; production hides it.)
- <http://localhost:8000/healthz> answers `{"status":"ok"}`.
- `--reload` restarts on every saved `.py` file.
- Emails are printed in this terminal (`EMAIL_BACKEND=console`). Look here for the
  verification link after signing up.

## 2.6 Start the web app (terminal 2)

```bash
cd web
npm install                              # first time, or when package.json changes
npm run dev                              # http://localhost:3000
```

In development Next.js forwards `/v1/...` to `localhost:8000` (`web/next.config.ts`), so
the browser only talks to port 3000, as it will in production.

Open <http://localhost:3000>: the public site. **Get started** creates a workspace.
Choose a business type; it decides which modules start switched on (chapter 1.2).

## 2.7 Demo data (optional, terminal 3)

Both scripts drive the real API, as a person would, so they also double as smoke tests.

```bash
cd api
uv run python -m scripts.demo_seed       # a small tea house: staff, attendance, leave, payroll
uv run python -m scripts.agency_week     # a 30-person agency's week: tasks, news, policies, approvals
```

Each prints the email and password to sign in with. `agency_week` signs thirty people in,
so set `LOGIN_LIMIT_PER_IP=1000` first (or wait five minutes between runs).

Inside the app, any new workspace also offers **sample data** on its first-day checklist
(Home), which you can remove again with one click.

## 2.8 Calling the scheduled jobs by hand

In production a scheduler calls `/internal/*` endpoints (chapter 3.9). Locally nothing
calls them, so things like the daily digest or automation schedules never fire unless you
do. With `INTERNAL_TOKEN=devtoken` in `.env` (restart the API after changing it):

```bash
H='X-Internal-Token: devtoken'
curl -X POST -H "$H" localhost:8000/internal/outbox/dispatch        # retry side effects
curl -X POST -H "$H" localhost:8000/internal/webhooks/tick          # send due webhooks
curl -X POST -H "$H" localhost:8000/internal/automations/tick       # run due automations
curl -X POST -H "$H" localhost:8000/internal/notifications/digest   # daily unread email
curl -X POST -H "$H" localhost:8000/internal/reports/send           # weekly/monthly reports
curl -X POST -H "$H" localhost:8000/internal/maintenance/daily      # clean expired rows
cd api && uv run python -m app.jobs.maintenance                     # nightly purge job
```

Without the header, or with a wrong one, they answer 404 on purpose.

## 2.9 Stopping and starting again

`Ctrl+C` in each terminal. Next time:

```bash
sudo service postgresql start                                  # if it isn't running
cd api && uv run uvicorn app.main:app --reload --port 8000     # terminal 1
cd web && npm run dev                                          # terminal 2
```

After `git pull`: `uv sync && uv run alembic upgrade head` in `api/`, `npm install` in `web/`.

## 2.10 Running it like production, locally

The development server is forgiving; production is a static export with strict security
headers. To see exactly what users will get:

```bash
cd web
npm run build          # static export into web/out + per-page CSP headers (scripts/csp.mjs)
npm run serve          # serves web/out like Cloudflare Pages, proxying /v1 to :8000
```

The browser tests (chapter 9) run against this build.

## 2.11 Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `connection refused` on port 5432 | Postgres isn't running: `sudo service postgresql start` |
| `password authentication failed for user "cm_app"` | roles missing: run `scripts/dev-db.sh` |
| `relation "…" does not exist` | migrations not applied: `cd api && uv run alembic upgrade head` |
| The web app loads but every call fails | the API isn't running, or you opened port 8000 instead of 3000 |
| "Too many attempts" when signing in | rate limit: wait 5–15 minutes or raise `LOGIN_LIMIT_PER_IP` locally |
| `cannot load library 'libpango…'` | install Pango (2.1); only payslip PDFs need it |
| AI screens say the assistant isn't set up | set `AI_PROVIDER=fake` or `GEMINI_API_KEY`, restart the API, then Settings → AI assistant |
| `check.sh` fails at "web types match the backend" | you changed the API: run `scripts/gen-api-types.sh` and commit the result |
| `alembic check` says there are new operations | models and migrations disagree: write a migration (chapter 4.6) |
| `MissingGreenlet` in the API | you touched a lazy relationship or an expired row in async code; load it in the query or `await db.refresh(row)` |
| A raw SQL query as `cm_owner` returns no rows | row-level security applies to the owner too (`FORCE`): run `SELECT set_config('app.tenant_id', '<uuid>', false);` first |
| Playwright can't find a browser | `npx playwright install chromium` once |
| The books show nothing after a sale | accounting must be switched on for the workspace; postings are made when the request ends (chapter 3.8) |

## 2.12 Looking inside the database

```bash
psql postgresql://cm_owner:cm_owner@localhost:5432/companymgmt
```

```sql
\dt                                          -- list tables
SELECT id, name, slug FROM tenants;          -- tenants is a global table: no RLS
SELECT set_config('app.tenant_id', '<a tenant id>', false);
SELECT full_name FROM employees LIMIT 5;     -- tenant tables now show that workspace
```
