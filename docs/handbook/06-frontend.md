# 6. The frontend

## 6.1 One Next.js project, exported as static files

`web/` holds the public site and the product. In development `npm run dev` runs a Next.js
server that forwards `/v1` to the API (`next.config.ts`). For production `npm run build`
writes plain files to `web/out/` (`output: "export"`): HTML, JS and CSS that Cloudflare
Pages serves. There is no Node server in production, nothing to patch, and hosting is free.

The consequence: **every product page renders in the browser** (`"use client"` at the
top) and fetches its data from `/v1`. Server components, server actions and API routes
from Next.js are not used.

```
web/
├── next.config.ts            static export in production; /v1 rewrite in development
├── src/
│   ├── app/
│   │   ├── layout.tsx        <html>, fonts, theme, providers
│   │   ├── globals.css       Tailwind + the design tokens (light, dark, accents, site theme)
│   │   ├── (site)/           public pages: /, /pricing, /developers, /security, /terms, /privacy, /dpa, /subprocessors
│   │   └── (product)/        /login, /signup, /join, /invite, /verify-email, /forgot-password,
│   │       │                 /reset-password, /change-password, /sso/callback, /till
│   │       └── app/          the signed-in product: /app, /app/pos, /app/leave, … /app/settings
│   ├── components/           React components; ui/ = design-system pieces; one folder per area
│   ├── api/                  client.ts (fetch wrapper), schema.d.ts (generated), types.ts, hooks.ts
│   ├── auth/                 session.tsx (who's signed in), guards.tsx (page access)
│   ├── i18n/                 en.ts, bn.ts, index.ts
│   ├── lib/                  small pure helpers with unit tests (money, dates, weeks, geolocation…)
│   └── data/plans.json       plan table for the public pricing page
├── public/                   icon, theme-init.js (runs before paint), screens/, .well-known/security.txt
├── functions/v1/[[path]].js  the Cloudflare Pages Function that proxies /v1 to the API
├── scripts/csp.mjs           writes out/_headers with a CSP per page after the build
├── scripts/serve.mjs         serves out/ locally the way Cloudflare does, with the /v1 proxy
├── e2e/                      Playwright browser journeys
└── playwright.config.ts, vitest.config.ts, eslint.config.js, tsconfig.json
```

**Routing is folders.** `src/app/(product)/app/leave/page.tsx` is `/app/leave`. Folders
in parentheses are route groups: they share a `layout.tsx` but don't appear in the URL.
`(product)/app/layout.tsx` wraps every app page in the **app shell**
(`components/app-shell.tsx`): the side rail on desktop, the bottom bar on phones, the
header with search (`command-palette.tsx`), the bell (`notifications.tsx`), the language
and account menus. The rail's items come from `components/nav-items.ts`, filtered by the
person's permissions and the workspace's modules.

State that should survive a reload or be linkable lives in the URL: `?tab=` (with
`lib/use-tab.ts`), `?task=` for the task panel, and so on.

Learn: [React — Learn](https://react.dev/learn), [Next.js App Router](https://nextjs.org/docs/app),
[static exports](https://nextjs.org/docs/app/guides/static-exports),
[TypeScript in 5 minutes](https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes.html).

## 6.2 Talking to the API

`src/api/client.ts`:

- `api<T>(path, { method, body, query, version, idempotencyKey })` adds
  `Authorization: Bearer <access token>`, sends `If-Match` when you pass `version`,
  parses JSON, and throws `ApiError` (`status`, `code`, `errors[]`) for problem responses.
- On a 401 it calls `/v1/auth/refresh` once (the refresh cookie travels automatically)
  and retries. Concurrent refreshes share one promise.
- The access token is only in memory: a reload signs in again through the refresh cookie.
- `download(path, query, filename)` saves files (payslips, exports, CSVs).

`src/api/schema.d.ts` is **generated** from the API's OpenAPI document by
`scripts/gen-api-types.sh`. Never edit it. `src/api/types.ts` gives the generated shapes
friendly names (`export type Task = S["TaskOut"]`). If you change the API, regenerate and
commit both `openapi.json` and `schema.d.ts`; `check.sh` fails otherwise.

**TanStack Query** caches server data:

```tsx
const { data, isLoading } = useQuery({ queryKey: ["leave", "requests", filters],
                                       queryFn: () => api<LeaveRequest[]>("/v1/leave/requests", { query: filters }) });

const approve = useMutation({
  mutationFn: (id: string) => api(`/v1/leave/requests/${id}/approve`, { method: "POST" }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["leave"] }),   // refetch lists
});
```

Shared hooks and keys are in `src/api/hooks.ts`; each feature keeps its own in
`components/<area>/data.ts` (for example `components/shop/data.ts`).

Learn: [TanStack Query overview](https://tanstack.com/query/latest/docs/framework/react/overview),
[invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation).

## 6.3 Who's signed in

`src/auth/session.tsx` provides `useSession()`: the user, the current workspace, and the
helpers every screen uses — `can("leave.approve")`, `hasModule("payroll")`. It loads
`/v1/auth/me` after a refresh. `src/auth/guards.tsx` protects pages (signed out → login;
password change required → `/change-password`). Hiding a button is for convenience only:
**the API is the real check**.

## 6.4 Forms

[react-hook-form](https://react-hook-form.com/get-started) everywhere:

```tsx
const { register, handleSubmit, setError, formState } = useForm<Values>({ defaultValues });
const onSubmit = handleSubmit(async (values) => {
  try { await save.mutateAsync(values); }
  catch (e) { if (!applyFieldErrors(setError, ["title", "body"], e)) toast.error(errorMessage(e)); }
});
<Field label={t("announcements.title")} error={formState.errors.title?.message}>
  <Input {...register("title")} />
</Field>
```

- `applyFieldErrors` (`lib/errors.ts`) puts the API's field errors next to their fields.
- When data arrives after the form opened, reset with
  `resetOptions: { keepDirtyValues: true }` so typing isn't wiped (a browser test checks).
- Read a live value with `useWatch({ control, name })`, not `watch()` (the linter enforces).

## 6.5 Design system

- Two looks: the **site** (teal, Plus Jakarta Sans headings, Inter text) and the
  **product** ("Atlas": white by default, dark mode, four accents — Plum, Saffron, Garnet,
  Ink). All colours are tokens in `src/app/globals.css` (`bg-surface`, `text-muted`,
  `bg-accent-soft`, `text-danger-text`…), defined for light and dark. Use tokens, never
  raw colours, and both modes stay WCAG AA.
- `public/theme-init.js` applies the saved theme before first paint (no flash).
- `src/components/ui/`: `Button`, `Input`, `Select`, `Field` (label, help and error wired
  for screen readers), `Dialog` / `SheetContent` (dialogs on desktop, sheets on phones),
  `Tabs`, `Table`, `Badge`, `Card`, `Alert`, `Menu`, `ConfirmDialog`, `Password`,
  `Spinner`, `Avatar`, `Choice`. Most wrap [Radix](https://www.radix-ui.com/primitives)
  primitives, which handle keyboard and screen readers.
- Icons: [lucide-react](https://lucide.dev/icons/). Toasts: `sonner`.
- The house rules (calm screens, little text, one clear next action) are in `CLAUDE.md`.

## 6.6 Two languages

Every visible string is a key: `t("leave.approve")`. Texts live in `src/i18n/en.ts` and
`src/i18n/bn.ts`; the Bangla file is typed against the English one, so a missing key fails
`npm run typecheck`. Plurals use `_one` / `_other` and `count`. Numbers and dates go
through `lib/format.ts` (`formatNumber`, `formatDay`; Bangla digits in Bangla). Money
through `lib/money.ts` (minor units in, formatted text out). Help-centre articles are in
`components/help/articles.ts`, in both languages.

Learn: [react-i18next](https://react.i18next.com/), [plurals](https://www.i18next.com/translation-function/plurals).

## 6.7 Security in the browser

- `scripts/csp.mjs` hashes each page's scripts after the build and writes `out/_headers`
  with a **per-page Content Security Policy** plus HSTS, frame, referrer and permission
  headers. So: **no inline scripts, no `dangerouslySetInnerHTML`, no third-party scripts**
  (Turnstile is the one allowed origin on sign-in pages). Code that must run before paint
  goes in `public/*.js`.
- Tokens never touch `localStorage`. The till's device token and offline sales are the
  only things stored on the device, by design.
- The browser tests fail on any CSP violation.

## 6.8 Offline and the till

`/app/pos` keeps unsent sales in the browser's `localStorage` (`components/shop/data.ts`) when the network drops and
sends them later with their `client_id`; the server keeps each once. `/till` is the PIN pad
for a registered shared device (`components/shop/tills.tsx`).

## 6.9 Commands

```bash
cd web
npm run dev          # http://localhost:3000, hot reload, /v1 → :8000
npm run lint         # ESLint (zero warnings allowed)
npm run typecheck    # TypeScript
npm test             # Vitest unit tests (src/**/*.test.ts)
npm run build        # static export into out/ + per-page security headers
npm run serve        # serve out/ like Cloudflare, /v1 → :8000
npx playwright test  # browser journeys (chapter 9)
../scripts/gen-api-types.sh   # regenerate API types after changing the API
```
