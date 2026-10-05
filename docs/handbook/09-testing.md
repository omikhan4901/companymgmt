# 9. Testing

## 9.1 The rule

```bash
scripts/check.sh            # lint, format, types, import layers, migrations, API contract,
                            # API tests, web types match the API, web lint/types/unit tests, build
E2E=1 scripts/check.sh      # plus the Playwright browser journeys
```

**Only push to `main` when it passes.** GitHub Actions are switched off (chapter 11.1),
so this script on your computer is the only gate. A full run takes about 10 minutes
(about 15 with `E2E=1`).

Numbers on 5 October 2026: **321 API tests, 91% line and branch coverage** (the gate is
85%), 33 web unit tests, 19 browser journeys on desktop plus the newer platform and shop
journeys, no breaking changes to the public API.

## 9.2 API tests (pytest)

- They run against a **real Postgres** (`companymgmt_test`), because row-level security
  can't be faked. The schema is built from the migrations once per run; tables are emptied
  before each test (`tests/conftest.py`).
- The app is called in-process through `httpx.AsyncClient` (no server needed).
- Emails go to the `memory` backend; `last_email(to)` and `link_token(mail)` read them.
- AI uses `provider.use_model(FakeModel(script=[…]))`.

Helpers in `tests/helpers.py`:

| Helper | Does |
|---|---|
| `signup(client, …)` | creates a workspace, returns an `Account` (`.get/.post/.patch/.put/.delete` with its token, `.tenant_id`, `.membership_id`) |
| `login(client, email)` | signs in an existing user |
| `add_staff(owner, …)` | a staff account without email |
| `invite_and_join(owner, role="manager", scope_department_id=…)` | invites, accepts, returns the new member's `Account` |
| `verify_email(account)` | confirms the email |
| `role_id(account, key)` | a built-in role's id |
| `if_match(version)` | the `If-Match` header for versioned writes |

A typical test reads like a story:

```python
async def test_managers_only_approve_their_own_department(client):
    owner = await signup(client)
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    ...
    r = await manager.post(f"/v1/leave/requests/{other_request}/approve")
    assert r.status_code == 404          # outside their scope: not even visible
```

Special tests worth knowing:

| Test | Guards |
|---|---|
| `test_isolation.py` | every tenant table has forced RLS; every id route, called with another workspace's ids, returns 404/422 and changes nothing |
| `test_platform.py` | every route declares its access; the public list is exactly as expected; schema names unique |
| `test_capabilities.py` | every AI read capability = its REST route, for owner, scoped manager, employee |
| `test_api_contract.py` | the public `/v1` contract has no breaking changes |
| `test_payroll_calc.py`, `test_ledger.py` | Hypothesis property tests: pay maths invariants; books always balance and stock always reconciles over thousands of random operations |
| `test_agency_week.py` | a 30-person agency's whole week through the API |
| `test_site_prices.py` | the public pricing page matches the plans in the database |

Gotcha: raw SQL in a test (to fake time, change a plan) must first run
`SELECT set_config('app.tenant_id', '<id>', false)`, because RLS applies to the owner role
too; otherwise the update silently touches nothing.

```bash
cd api
uv run pytest -q                                   # everything (~8 min)
uv run pytest -q tests/test_leave.py --no-cov      # one file, skip the coverage gate
uv run pytest -q -k "approve and not reject" -x -s # by name, stop at first failure, show prints
```

## 9.3 Web unit tests (Vitest)

`web/src/**/*.test.ts`: money, dates, weeks, time zones, geolocation, navigation, the
API client, WhatsApp links, help articles. `npm test` in `web/`.

## 9.4 Browser journeys (Playwright)

`web/e2e/*.spec.ts` drive Chromium against the **production build** with its real security
headers (`scripts/serve.mjs`) and the real API (started by `playwright.config.ts` with the
proxy token, so `/v1` is reached exactly as in production). Projects: `desktop` and `phone`.

Every page visited is checked by:

- `expectAccessible(page, label)`: axe WCAG 2.2 AA, plus no sideways scrolling;
- `watchCsp(page)`: no Content Security Policy violations.

Journeys: sign-up to clock-in (with location), leave, payroll, tasks, announcements,
documents, approvals, onboarding, imports, reports, data export/delete/restore, the AI
assistant (fake model), a 30-person agency's week, the developer and security settings,
and a shop selling at the till and opening the books.

```bash
cd web
npm run build
npx playwright test                                  # all, both screen sizes
npx playwright test e2e/shop.spec.ts --project=desktop
npx playwright test --ui                             # watch it step by step
npx playwright show-trace test-results/…/trace.zip   # after a failure
```

Helpers (`e2e/helpers.ts`): `signUp`, `signIn`, `addStaff`, `staffSignIn`, `setPlan(email,
plan)` (via `psql`), `uniqueEmail`. Prefer `getByRole` and `getByLabel` locators.

## 9.5 What tests can't cover yet

Listed in `docs/UNTESTED.md`: real Gemini, real identity providers, real passkeys, real
SMTP, webhooks to a real server, and anything about the deployment itself.

## 9.6 Writing a test for your change

1. Find the closest existing test file and copy a test's shape.
2. Set up the smallest company that shows the rule (an owner, maybe a manager and a staff
   member in two departments).
3. Act through the API as each person.
4. Assert on what each person sees, including what they must **not** see (404) and what
   they may not do (403/402/409/412).
5. For a new id route, nothing extra: the isolation sweep finds it. Make sure it returns
   404 for another workspace's id (load the parent first).
