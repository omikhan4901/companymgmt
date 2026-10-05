# Legal review (October 2026)

> **Not legal advice.** This is a product-side review written to brief a lawyer: what the
> product does with data and money, what similar companies promise in their legal
> documents, where our drafts fall short, and what was changed. A qualified lawyer in
> Bangladesh (and in any country we sell into) must review it before launch, and the
> drafts on the website stay marked "Draft pending legal review" until then.

## 1. What changed since the first drafts (30 Sep 2026)

The first terms and privacy policy described an HR and attendance tool. Since then the
product grew to cover things with real legal weight:

| Area | What the product now does | Why it matters legally |
|---|---|---|
| Payroll | Salary, deductions, Bangladesh tax table (editable), payslips (PDF) | Salary is sensitive financial data; wrong pay or tax causes real loss; record-keeping duties (Labour Act) |
| Point of sale | Sales, receipts, returns, voids, cash drawers, offline sales queue, taxes the business configures | The business, not us, is responsible for tax (VAT/SD) and receipts; we must never claim the receipts are statutory invoices (Mushak) |
| Customers & dues, suppliers | Who owes what, statements, payments | Third parties' personal data (customers of our customers) |
| Expenses & receipts | Photos/PDFs of receipts | Files may contain personal data |
| Inventory & accounting | Double-entry books, P&L, balance sheet, tax-return templates the business's accountant builds | Not accounting/tax advice; the business's accountant is responsible for returns |
| AI assistant (Gemini) | Answers, writing help, summaries, proposed actions, automations drafting, early-warning signals | Data goes to Google as a sub-processor; outputs can be wrong; people signals are a form of employee profiling |
| Location check | Position at clock-in/out only, rounded to ~11 m | Employee monitoring: proportionality, notice, possibly consent and an impact assessment |
| Developer platform | API keys, webhooks, SCIM, company sign-in (OIDC), sandbox | The customer sends data to *their* systems; we need terms for API use, rate limits, and deprecation |
| Tills & PINs | Shared devices with cashier PINs | Shared-device security is partly the customer's responsibility |
| Documents & announcements | Policies with acknowledgements, read receipts | Acknowledgements may be used as evidence; we should not promise they are legally binding signatures |
| Audit log | Tamper-evident hash chain, export | Must be described as tamper-*evident*, not "immutable" or notarised |
| Data rights | Full export, personal export, deletion with 30-day restore and a signed certificate, retention by plan | Good; must match what the documents promise |

## 2. How similar companies handle this

Direct fetching of competitors' legal pages was blocked from this environment, so this
section relies on search summaries of their published documents. Quotes are paraphrased;
the lawyer should read the originals.

| Topic | What similar services do | Sources |
|---|---|---|
| **Roles** | HR SaaS act as *processor*; the customer is *controller* of employee data, with a separate Data Processing Addendum (DPA). The provider is controller only for its own account, billing and security data. | Freshworks, JazzHR/Employ, Employment Hero, HR365 DPAs |
| **DPA content** | Article 28 GDPR items: documented instructions, confidentiality, security measures annex, sub-processor flow-down, help with data-subject requests, breach notice, deletion/return at the end, audits. | GDPR Art. 28 guides (Irish DPC, secureprivacy.ai, legiscope) |
| **Sub-processors** | A public list, general written authorisation, **30 days' notice** of changes with a right to object. | Varonis, LogicMonitor, Freshworks DPAs |
| **After termination** | **30 days** to export, then deletion; backups age out. Payroll providers keep payroll records longer where tax law requires (BambooHR: 7 years for payroll services). | BambooHR ToS, SaaS contract guides |
| **AI** | AI off by default, customer switches it on; customer data **not used to train** models; AI output belongs to the customer; providers named (BambooHR names OpenAI and Cohere in an AI Addendum). | BambooHR AI Addendum, AI principles |
| **Gemini API** | On the paid tier Google doesn't use prompts or responses to improve its products and processes them under its processor DPA; it logs them for a limited time only to detect abuse. The free tier may be used for training and human review. | Gemini API Additional Terms |
| **POS & tax** | Merchants are solely responsible for configuring, charging, collecting and remitting taxes; providers give no warranty that tools meet a jurisdiction's tax rules and don't give tax advice (Square, Toast). Merchants keep receipts as the law requires. | Square, Toast, Shift4 terms |
| **Liability** | Cap at fees paid in the previous 12 months; carve-outs for indemnities and confidentiality are common in B2B. | SaaS contract guides |
| **Location** | Regulators accept clock-in/out location to verify attendance at a site as proportionate; continuous tracking is not. Employee monitoring is high risk under GDPR and needs a DPIA. | CNIL/EU guidance summaries, Italian Garante fines |

## 3. The law that applies (first market: Bangladesh)

### Personal Data Protection Ordinance 2025 (Bangladesh)

From commentary on the Ordinance (to be confirmed against the gazetted text):

- Consent must be free, specific, informed, unambiguous and withdrawable; people must be
  told the **purpose, retention period, who data is transferred to, and how to withdraw**
  at or before collection.
- Security measures (encryption, pseudonymisation, resilience, restore, regular testing).
- Keep data no longer than needed; keep **records of processing for at least 5 years**.
- The controller ("data fiduciary") is liable for its processors.
- **Breaches reported to the authority, reportedly within 72 hours.**
- **Cross-border transfers** only with equivalent protection or one of the listed grounds
  (consent, a contract for goods/services, the person's interests); data classified as
  "confidential" or "restricted" must stay in Bangladesh.
- Fines reportedly 1–2% of turnover (2–5% for significant fiduciaries); criminal penalties
  exist. Enforcement provisions start about 18 months after gazettement (around May 2027).

**Impact on us:** we host in Singapore (Google Cloud `asia-southeast1`, Neon, Cloudflare).
Our customers (controllers) need a lawful ground for transferring their staff's and
customers' data to us abroad; the "contract for services" ground and equivalent-protection
safeguards should be written into the DPA. **Open question for the lawyer:** whether any
of our data (payroll, national ids) could fall under "confidential/restricted"
classification requiring local storage, and the official status and dates of the
Ordinance and its rules.

### Bangladesh Labour Act 2006 (as amended)

- Employers must keep records of personal details, wages, hours, leave and rest days.
  Payroll records shouldn't be deleted early: our deletion flow lets the *owner* delete,
  and our terms must say the customer is responsible for keeping records the law requires
  (export before deleting).
- No specific rule found on location tracking; under the Ordinance, staff must be told.

### VAT and Supplementary Duty Act 2012 (Bangladesh)

- Registered businesses issue VAT invoices in prescribed forms (Mushak). Our receipts are
  **not** Mushak forms and our tax-return templates are tools for the business's
  accountant. The terms must say so plainly.

### Customers abroad

- **EU/UK customers (GDPR):** we're a processor; needs a GDPR-grade DPA with Standard
  Contractual Clauses for transfers out of the EU (Singapore has no adequacy decision).
  Employee location monitoring needs the customer's DPIA.
- Other countries: the terms should say customers are responsible for local employment,
  tax and privacy compliance.

## 4. Gaps found in the first drafts

| # | Gap | Severity | Fixed in the new drafts? |
|---|---|---|---|
| G1 | Terms describe only "people and attendance": nothing on payroll, POS, accounting, AI, API | High | ✅ Service description covers all modules |
| G2 | No Data Processing Addendum | High | ✅ `/dpa` page (draft) |
| G3 | No sub-processor list or change notice | High | ✅ `/subprocessors` page, 30 days' notice |
| G4 | No tax/accounting/payroll disclaimer (we don't give tax advice; the business configures taxes and is responsible for returns, receipts and payslips) | High | ✅ "Calculations and records" section |
| G5 | AI: no terms beyond the in-app notice (provider, no training, output accuracy, human confirmation, people signals) | High | ✅ "AI features" section + privacy section |
| G6 | Termination: no export window or deletion timeline after an account ends | Medium | ✅ 30-day export window, then deletion; backups 35 days |
| G7 | API/webhooks/SCIM: no API terms (rate limits, key security, deprecation, customer responsible for its endpoints) | Medium | ✅ "API and integrations" section |
| G8 | Customers' customers (dues, receipts) not mentioned in the privacy policy | Medium | ✅ Data categories extended |
| G9 | Cross-border transfer not explained (Singapore) | Medium | ✅ Privacy "Where it's stored" + DPA transfers |
| G10 | Breach notification promise missing | Medium | ✅ DPA: without undue delay, aim within 48 hours of confirming |
| G11 | Location check: no statement of the employer's duty to inform staff / assess | Medium | ✅ Customer responsibilities |
| G12 | Liability: no carve-outs, no indemnity from the customer for unlawful data/use | Medium | ✅ Mutual-ish structure; lawyer to tune |
| G13 | No suspension/fair-use, no acceptable use detail (e.g. no unlawful surveillance) | Low | ✅ |
| G14 | No changes-to-terms notice period | Low | ✅ 30 days for material changes |
| G15 | "Immutable" wording risk for the audit log | Low | ✅ "tamper-evident" everywhere |
| G16 | Payment terms for when billing launches (taxes on fees, refunds, renewals) | Low (billing on hold) | 🟡 Placeholder; finish with M5 |
| G17 | Age: "at least 18" for account holders; staff accounts may include minors where the law allows employment | Low | ✅ Owners/admins 18+; workspace decides staff |
| G18 | Security page referenced by security.txt didn't exist | Low | ✅ `/security` page |

## 5. Decisions for the owner and the lawyer

1. **Entity.** The terms name an individual (Mehboob Ehsan Khan, Dhaka). Selling to
   businesses as a sole proprietor exposes personal assets; consider a private limited
   company before launch and update every document.
2. **Governing law and courts:** Bangladesh / Dhaka for now; for EU customers the DPA
   must follow GDPR regardless.
3. **Liability cap:** 12 months' fees (common). Consider a minimum floor (e.g. USD 100) so
   free-plan users aren't at zero, and carve-outs for our confidentiality and data
   protection breaches, as enterprise buyers will ask.
4. **Payroll record retention after deletion:** we delete everything after the 30-day
   restore window. Some providers keep payroll records for years for tax law. Decide
   whether to keep a minimal payroll archive (and say so) or keep the current "export
   first, the customer keeps records" approach (current drafts).
5. **Data localisation** under the Ordinance (see §3).
6. **AI:** confirm the Gemini *paid* tier is used in production (the free tier allows
   Google to train on and review prompts). The deploy runbook says to use a billed
   project; the privacy policy now relies on that.
7. **Status of acknowledgements:** document acknowledgements are records that someone
   clicked "I've read this", not electronic signatures under the ICT Act; say so if
   customers use them as evidence.
8. **Insurance:** professional indemnity / cyber cover before taking enterprise customers.

## 6. What was changed on the website

- `/terms`: rewritten (draft) — service, accounts, customer data, customer
  responsibilities (staff notice, location, taxes, records), calculations and records
  disclaimer, AI features, API and integrations, acceptable use, plans and fees, suspension,
  termination and export, warranties, liability, indemnity, changes, law.
- `/privacy`: rewritten (draft) — two roles, every data category including customers'
  customers and AI, purposes and legal grounds, sub-processors and transfers, retention
  table, security, rights, children, changes.
- `/dpa`: new (draft) — processor terms modelled on GDPR Art. 28 and the Ordinance.
- `/subprocessors`: new — the list and the 30-day notice promise.
- `/security`: new — the security overview and how to report a vulnerability.

## Sources

- [Bangladesh PDPO 2025: key takeaways (The Daily Star)](https://www.thedailystar.net/tech-startup/news/bangladeshs-personal-data-protection-ordinance-2025-key-takeaways-4015401)
- [PDPO 2025 compliance (bd-scl.com)](https://bd-scl.com/insights/personal-data-protection-ordinance-2025-compliance.html)
- [Key highlights of the PDPO 2025 (Mahbub & Company)](https://mahbub-law.com/key-highlights-of-the-personal-data-protection-ordinance-2025-for-businesses/)
- [DataGuidance: PDPO 2025 obligations](https://www.dataguidance.com/opinion/bangladesh-data-protection-ordinance-2025-key-part-two)
- [Lex Mundi: Bangladesh data privacy guide](https://www.lexmundi.com/guides/data-privacy-guide/jurisdictions/asia-pacific/bangladesh/)
- [Bangladesh Labour Act 2006 (MCCI copy)](https://mccibd.org/wp-content/uploads/2021/09/Bangladesh-Labour-Act-2006_English-Upto-2018.pdf)
- [Lexology: labour and employment law in Bangladesh](https://www.lexology.com/library/detail.aspx?g=d1623485-d48f-439e-bf10-61afd82a80db)
- [BambooHR Terms of Service](https://www.bamboohr.com/legal/terms-of-service) and [AI Addendum](https://www.bamboohr.com/legal/bamboohr-artificial-intelligence-addendum)
- [Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms)
- [Freshworks DPA](https://www.freshworks.com/data-processing-addendum/), [JazzHR DPA](https://www.jazzhr.com/data-processing-addendum/), [Employment Hero DPA](https://employmenthero.com/legals/data-processing-addendum-07-07-2025/), [HR365 DPA](https://www.hr365.us/trust-center/data-processing-addendum/), [LogicMonitor DPA](https://www.logicmonitor.com/legal/data-processing-addendum)
- [Irish DPC: controllers and processors](https://www.dataprotection.ie/en/organisations/know-your-obligations/controller-and-processor-relationships), [SaaS DPA guide](https://secureprivacy.ai/blog/data-processing-agreements-dpas-for-saas)
- [Toast merchant agreement](https://pos.toasttab.com/merchant-agreement), [Shift4 POS terms](https://www.shift4.com/pdf/POS-System-Service-Agreement.pdf), [Loyverse: how taxes are calculated](https://help.loyverse.com/help/how-taxes-are-calculated)
- [GDPR and geolocation time tracking (Cleverfy)](https://www.cleverfy.es/en/blog/is-geolocation-time-tracking-legal/), [Garante fine for GPS monitoring](https://www.dsn-group.com/privacy-notes/garante-fine-for-employee-monitoring-and-gps-tracking-4953075)
- [SaaS data export on termination (TermScore)](https://www.termscore.com/insights/saas-vendor-rights/saas-data-export-restrictions-contract-rights)
