/**
 * CompanyMgmt API client (Node 18+, Deno, Bun, browsers for public calls).
 *
 * - Authenticates with an API key (`cmk_...`).
 * - Retries network errors, 429 and 5xx with backoff; writes carry an Idempotency-Key so
 *   a retry never does the work twice.
 * - `paginate()` walks `{ items, next_cursor }` lists.
 * - `verifyWebhook()` checks the `CompanyMgmt-Signature` header.
 * - Errors throw `CompanyMgmtError` with the problem document's `status` and `code`.
 */

export interface Problem {
  type?: string;
  title?: string;
  status: number;
  detail?: string;
  code?: string;
  errors?: { field: string; message: string }[];
  request_id?: string;
}

export class CompanyMgmtError extends Error {
  readonly status: number;
  readonly code: string;
  readonly problem: Problem;
  constructor(problem: Problem) {
    super(problem.detail ?? problem.title ?? `HTTP ${problem.status}`);
    this.name = "CompanyMgmtError";
    this.status = problem.status;
    this.code = problem.code ?? "error";
    this.problem = problem;
  }
}

export interface Options {
  apiKey: string;
  baseUrl?: string;
  /** Tries for retryable failures (default 3). */
  maxRetries?: number;
  fetch?: typeof fetch;
  timeoutMs?: number;
}

type Query = Record<string, string | number | boolean | undefined>;

const RETRYABLE = new Set([408, 425, 429, 500, 502, 503, 504]);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export class CompanyMgmt {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly maxRetries: number;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: Options) {
    if (!options.apiKey?.startsWith("cmk_")) throw new Error("Pass an API key (cmk_...).");
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? "https://companymgmt.app/v1").replace(/\/$/, "");
    this.maxRetries = options.maxRetries ?? 3;
    this.fetchImpl = options.fetch ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 30_000;
  }

  async request<T = unknown>(
    method: string,
    path: string,
    init: { query?: Query; body?: unknown; ifMatch?: number; idempotencyKey?: string } = {},
  ): Promise<T> {
    const url = new URL(this.baseUrl + (path.startsWith("/") ? path : `/${path}`));
    for (const [k, v] of Object.entries(init.query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v));
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      Accept: "application/json",
    };
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
    if (init.ifMatch !== undefined) headers["If-Match"] = `W/"${init.ifMatch}"`;
    if (method !== "GET") headers["Idempotency-Key"] = init.idempotencyKey ?? newKey();

    for (let attempt = 0; ; attempt++) {
      let response: Response | undefined;
      try {
        response = await this.fetchImpl(url, {
          method,
          headers,
          body: init.body === undefined ? undefined : JSON.stringify(init.body),
          signal: AbortSignal.timeout(this.timeoutMs),
        });
      } catch (error) {
        if (attempt >= this.maxRetries) throw error;
      }
      if (response && response.ok) {
        if (response.status === 204) return undefined as T;
        const type = response.headers.get("content-type") ?? "";
        return (type.includes("json") ? await response.json() : await response.text()) as T;
      }
      if (response && (!RETRYABLE.has(response.status) || attempt >= this.maxRetries)) {
        let problem: Problem = { status: response.status };
        try {
          problem = { status: response.status, ...(await response.json()) };
        } catch {
          /* not JSON */
        }
        throw new CompanyMgmtError(problem);
      }
      const retryAfter = Number(response?.headers.get("retry-after"));
      await sleep(retryAfter > 0 ? retryAfter * 1000 : Math.min(8000, 250 * 2 ** attempt));
    }
  }

  get<T = unknown>(path: string, query?: Query) {
    return this.request<T>("GET", path, { query });
  }
  post<T = unknown>(path: string, body?: unknown, opts: { idempotencyKey?: string } = {}) {
    return this.request<T>("POST", path, { body, ...opts });
  }
  put<T = unknown>(path: string, body: unknown, opts: { ifMatch?: number } = {}) {
    return this.request<T>("PUT", path, { body, ...opts });
  }
  patch<T = unknown>(path: string, body: unknown, opts: { ifMatch?: number } = {}) {
    return this.request<T>("PATCH", path, { body, ...opts });
  }
  delete<T = unknown>(path: string) {
    return this.request<T>("DELETE", path);
  }

  /** Every item of a cursor-paged list. */
  async *paginate<T = Record<string, unknown>>(path: string, query: Query = {}): AsyncGenerator<T> {
    let cursor: string | undefined;
    do {
      const page = await this.get<{ items: T[]; next_cursor: string | null }>(path, { ...query, cursor });
      yield* page.items;
      cursor = page.next_cursor ?? undefined;
    } while (cursor);
  }
}

function toHex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function equal(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** Checks `CompanyMgmt-Signature` against the raw request body (Web Crypto, so it runs
 * in Node 18+, Workers, Deno and Bun). Refuses signatures older than `toleranceSeconds`. */
export async function verifyWebhook(
  secret: string,
  rawBody: string | Uint8Array,
  header: string,
  toleranceSeconds = 300,
  now = Date.now() / 1000,
): Promise<boolean> {
  const parts = Object.fromEntries(
    header.split(",").map((p) => {
      const i = p.indexOf("=");
      return [p.slice(0, i).trim(), p.slice(i + 1).trim()];
    }),
  );
  const t = Number(parts.t);
  if (!Number.isFinite(t) || Math.abs(now - t) > toleranceSeconds || !parts.v1) return false;
  const encoder = new TextEncoder();
  const body = typeof rawBody === "string" ? encoder.encode(rawBody) : rawBody;
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
  ]);
  const prefix = encoder.encode(`${t}.`);
  const message = new Uint8Array(prefix.length + body.length);
  message.set(prefix);
  message.set(body, prefix.length);
  return equal(toHex(await crypto.subtle.sign("HMAC", key, message)), parts.v1);
}
