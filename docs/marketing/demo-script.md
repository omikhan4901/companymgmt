# Demo video script (about 90 seconds)

Setup: run `api/scripts/demo_seed.py` for the owner workspace. Record the laptop at 1440×900
and a phone (or Chrome's device mode at 390×844). Quiet background, no music needed.

| Time | Screen | Say |
|---|---|---|
| 0:00 | Landing page hero | "Small businesses in Bangladesh still track attendance on paper. I built CompanyMgmt so a tea stall and a large company can use the same tool." |
| 0:08 | Sign-up: language cards, then business type cards | "Sign-up asks three simple questions: language, you, your business. A tea stall gets a simpler screen than a factory." |
| 0:18 | Home: big **Clock in** button, press it | "For most people it's one button." |
| 0:23 | Team → **Add staff without email** → the one-time code, username and password | "Many staff don't have email, so the owner creates a username. The password is shown once, and they must change it." |
| 0:33 | Phone, in Bangla: staff signs in, sets a password, clocks in | "Every screen works in Bangla, on a phone." |
| 0:43 | Attendance → Requests: Nadia's "My phone battery died" → **Approve** | "Forgot to clock in? You ask for a fix, a manager approves it, and it's recorded. Managers can't approve their own." |
| 0:53 | Timesheet for the month, then **Download CSV** | "Month-end is a timesheet you can trust, ready for Excel." |
| 1:00 | Settings → Audit log → **Check integrity** (green message) | "Every change goes into an audit log that can't be edited, and the app can prove it." |
| 1:08 | Code: `test_isolation.py`, terminal showing `105 passed` | "Behind it, each business's data is kept apart by Postgres row-level security. A test attacks every API route with another company's IDs." |
| 1:20 | README / architecture diagram | "FastAPI, React, Postgres on serverless infrastructure that costs nothing while idle. Next up: payroll, point of sale and inventory." |
| 1:28 | Logo | "CompanyMgmt." |

Keep cuts tight; skip typing by using pre-filled fields. Don't show real personal data.
