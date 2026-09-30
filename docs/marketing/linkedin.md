# LinkedIn post

> Our university group project had a login system that stored passwords with plain
> SHA-256 and shipped with admin/admin. 😅
>
> I rebuilt it from scratch as a real product: **CompanyMgmt**, attendance and team
> management that works for a tea stall with two staff or a company with branches, in
> English and বাংলা.
>
> What's in the first release:
> ⏱️ Clock in from any phone (overnight shifts and branch time zones handled)
> 🙋 Staff accounts without email
> ✅ Correction requests with manager approval
> 📊 Monthly timesheets and Excel-safe exports
> 🔐 Two-step verification, device list, tamper-evident audit log
>
> The part I'm proudest of is that each company's data is kept apart by PostgreSQL
> row-level security, not just by application code. A test attacks every API route with
> another company's IDs on every push.
>
> Behind it: 105 API tests at 90% coverage, browser tests on desktop and phone with
> automated accessibility checks, and serverless infrastructure that costs nothing while
> idle.
>
> Next: payroll, point of sale and inventory. Code and screenshots:
> github.com/omikhan4901/companymgmt
>
> #Python #FastAPI #PostgreSQL #React #SaaS #Bangladesh #WebSecurity

Post with 2–3 screenshots: the timesheet, the Bangla phone screen, the approvals screen.
