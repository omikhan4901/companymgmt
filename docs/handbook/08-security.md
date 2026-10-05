# 8. Security

The target is OWASP ASVS 5.0 level 2. The item-by-item checklist with the test that proves
each one is `docs/security/asvs-l2.md`; the AI threat model is `docs/security/ai.md`; how
to report a vulnerability is `SECURITY.md` and `/.well-known/security.txt`; incident steps
are `docs/runbooks/incident.md`. This chapter explains the protections and the rules you
must keep when you change code.

## 8.1 The ten rules never to break

1. **Every tenant table gets forced RLS** in its migration (`rls.tenant_table`). The
   isolation test will catch a missing one; don't silence it.
2. **The API connects as `cm_app`**, never as the owner or a superuser.
3. **Every route declares its access** (`public()`, `signed_in()`, `allow()`,
   `internal_only`). Public routes are a short, tested list.
4. **Check permissions in the service** too, and answer **404** for things outside the
   caller's scope.
5. **Never trust ids or tenant ids from the client** for whose data it is; the workspace
   comes from the session.
6. **No secrets in git**: `.env` is ignored; production secrets live in Secret Manager.
   `gitleaks` runs in `check.sh` when installed.
7. **No inline scripts or `dangerouslySetInnerHTML`** in the web app (CSP).
8. **Outbound HTTP to customer-chosen URLs only through `core/safehttp.py`** (blocks
   private addresses and DNS rebinding).
9. **Money in integers, files checked by content, CSV cells through `safe_cell`.**
10. **Modules never import `app.ai`**, and the AI only reaches data through capabilities,
    as the asker.

## 8.2 Accounts and sign-in

| Protection | Where |
|---|---|
| Argon2id password hashing, rehash when parameters change | `core/security/passwords.py` |
| 8–128 characters, any script, checked against 100,000 breached passwords | same; list in `security/data/` |
| Email verification before inviting others | `routes_auth.py`, `routes_workspace.py` |
| 10-minute EdDSA access tokens (algorithm pinned), in memory only | `core/security/tokens.py`, `web/src/api/client.ts` |
| Refresh tokens: random, stored hashed, `httpOnly; Secure; SameSite=Strict` cookie, rotated every use, reuse revokes the session (10 s grace for two tabs), idle 7 days, absolute 30 days | `platform/tokens.py` |
| Refresh needs the `X-CM-Client: web` header (blocks cross-site form posts) | `routes_auth.py` |
| Session list, "sign out other devices", revocation checked every request | `routes_auth.py`, `deps.py` |
| TOTP two-step with single-use recovery codes, secret encrypted; workspaces can require it for owners/admins | `core/security/totp.py` |
| Passkeys (WebAuthn, user verification required, clone detection) | `platform/passkeys.py` |
| Company sign-in (OIDC with PKCE, state, nonce, signature, issuer, audience, expiry checks); can be required | `platform/sso.py` |
| Step-up: sensitive actions need a sign-in within 5 minutes | `POST /v1/auth/reauth` |
| Rate limits per IP and per account; Turnstile after 5 failures; failures look identical | `core/ratelimit.py`, `core/captcha.py` |
| Reset links single use, 30 minutes; all sessions end on reset | `routes_auth.py` |
| New-device sign-in emails; sign-in records kept a year | `platform/tokens.py`, maintenance job |
| Till PINs only on registered devices, lockout, selling-only 12-hour sessions | `sales/tills.py` |
| API keys hashed, ≤ the maker's permissions, never owner-only, per-key rate limits, network ranges, expiry, rotation | `routes_developers.py`, `deps.py` |

## 8.3 Access control

- Roles → permissions → optional department scope (chapter 4.7).
- Membership and role reloaded every request: changes apply immediately.
- Nobody grants what they don't hold; the last owner can't be removed.
- Plan limits and read-only status are enforced in the same `check_access()` for REST
  and AI.
- Network allowlist per workspace (the owner can't lock themselves out).
- Four-eyes where money moves: payroll preparer ≠ finalizer; nobody approves their own
  leave or time fix.

## 8.4 Data protection

- **Isolation:** three layers (chapter 3.4), proven by the isolation sweep.
- **Field encryption:** national IDs, two-step secrets, a workspace's own AI key, SSO
  client secrets: AES-256-GCM with the row id as associated data (a value copied to another
  row won't decrypt), key ids for rotation (`FIELD_ENCRYPTION_KEYS`).
- **Audit log:** append-only for the app, hash-chained per workspace, anchors keep it
  verifiable after retention trims; `GET /v1/audit/verify` detects a direct database edit.
- **In transit:** HTTPS everywhere (Cloudflare, Cloud Run), HSTS; Neon with
  `sslmode=verify-full`.
- **At rest:** Neon, Cloud Run and R2 encrypt disks; backups are additionally encrypted
  with `age` to a key that never leaves your computer.
- **Retention:** deleted workspaces purged after 30 days with a signed certificate;
  audit entries by plan; sign-in records a year; notifications six months; webhook
  deliveries 30 days.

## 8.5 The web edge

- Per-page CSP with script hashes, `frame-ancestors 'none'`, HSTS, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy` (`web/scripts/csp.mjs`).
- The API adds its own strict headers to every response (`core/middleware.py`) and
  limits request sizes (1 MB JSON, per-route uploads).
- **The proxy token:** with `PROXY_TOKEN` set, the API refuses `/v1` requests that didn't
  come through the Pages Function, and takes the client IP only from it, so nobody can
  dodge per-IP rate limits by calling Cloud Run directly with a forged `X-Forwarded-For`.
- CORS allows only the web origin (and in production nothing needs it: same origin).

## 8.6 Inputs and outputs

- Pydantic validates every body; `In` rejects unknown fields; every string has a length
  limit; text is NFC-normalised and control characters removed.
- SQL only through SQLAlchemy or bound parameters.
- Uploads checked by magic bytes; Office files containing DTDs or entities refused before parsing (`documents/text.py`), unpacked size capped; downloads
  always `Content-Disposition: attachment`.
- CSV and spreadsheet exports neutralise formulas (`core/spreadsheet.py`).
- Error responses never include stack traces; each has a request id to find the log.

## 8.7 Outbound requests (SSRF)

Webhooks and SSO discovery go to addresses customers choose. `core/safehttp.py` resolves
the host, refuses private, loopback, link-local and metadata addresses, then connects to
**that** IP (with the right TLS name), so DNS can't be switched between the check and the
connection. HTTPS only, short timeouts, no redirects followed.

## 8.8 The AI

- Off unless a key is set **and** the workspace owner accepts the terms.
- The model only gets the asker's **read** capabilities; each runs as the asker.
- Tool results are wrapped as data; the system prompt says never to follow instructions
  inside them (tested with injected text).
- Writes are only proposals until the person confirms.
- At most six steps per question; allowances per plan.
- Paid Gemini tier only (no training on prompts) — a deployment rule in
  `runbooks/deploy.md`.

## 8.9 Dependencies and supply chain

- `uv.lock` and `package-lock.json` pin exact versions.
- `uv run pip-audit` and `npm audit --omit=dev` (both clean on 2026-10-05).
- Dependabot opens update pull requests (free, also on private repositories).
- Base images from `mirror.gcr.io`, upgraded at build, run as a non-root user.

## 8.10 What still needs a person

- A lawyer's review of the legal drafts (`docs/legal/REVIEW.md`).
- An OWASP ZAP scan and a penetration test against a real deployment.
- Real identity providers, real passkeys and real SMTP tried end to end.
- The daily audit-anchor upload to R2 (ASVS L2b) once R2 exists.
