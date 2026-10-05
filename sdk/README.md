# SDKs

Small clients for the CompanyMgmt API. Both do the same things: API-key auth, retries on
network errors / 429 / 5xx with backoff (writes keep one `Idempotency-Key` across retries,
so nothing happens twice), a pagination helper, `If-Match` for edits, errors as an
exception carrying the problem document's `status` and `code`, and webhook signature
verification. See [docs/api/README.md](../docs/api/README.md) for the API itself.

| | Folder | Test |
|---|---|---|
| TypeScript (Node 18+, Workers, Deno, Bun) | `typescript/` | `node --test --experimental-strip-types src/index.test.ts` (Node 22+) |
| Python 3.10+ (httpx) | `python/` | `PYTHONPATH=sdk/python pytest sdk/python/tests` |

They aren't published to npm/PyPI yet; vendor the folder or install from the repo
(`pip install ./sdk/python`, `npm install ./sdk/typescript && npm run build`).
