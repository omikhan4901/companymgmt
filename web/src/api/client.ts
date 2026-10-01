/**
 * API client. The access token lives only in memory; the refresh token is an httpOnly
 * cookie the browser sends to /v1/auth/refresh. On a 401 the client refreshes once and
 * retries. Errors come back as RFC 9457 problem details.
 */

export const API_URL: string = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: FieldError[];
  readonly body: Record<string, unknown>;

  constructor(status: number, body: Record<string, unknown>) {
    super(String(body.detail ?? body.title ?? "Something went wrong"));
    this.status = status;
    this.code = String(body.code ?? "error");
    this.errors = Array.isArray(body.errors) ? (body.errors as FieldError[]) : [];
    this.body = body;
  }
}

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const listeners = new Set<(signedIn: boolean) => void>();

export function setAccessToken(token: string | null): void {
  accessToken = token;
  listeners.forEach((fn) => fn(token !== null));
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

export function onAuthChange(fn: (signedIn: boolean) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function doRefresh(): Promise<boolean> {
  for (let attempt = 0; attempt < 3; attempt++) {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "x-cm-client": "web" },
      });
    } catch {
      return false;
    }
    if (response.ok) {
      const body = (await response.json()) as { access_token: string };
      setAccessToken(body.access_token);
      return true;
    }
    // Another tab refreshed at the same moment; its new cookie is already set.
    if (response.status === 409) {
      await sleep(250 * (attempt + 1));
      continue;
    }
    setAccessToken(null);
    return false;
  }
  return false;
}

/** Refresh the access token (one at a time, shared by concurrent callers). */
export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = doRefresh().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Sent as is (e.g. a file), instead of JSON. */
  rawBody?: Blob;
  query?: Record<string, string | number | boolean | undefined | null>;
  headers?: Record<string, string>;
  version?: number;
  signal?: AbortSignal;
  raw?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  return API_URL ? url.toString() : `${url.pathname}${url.search}`;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) };
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;
  if (options.body !== undefined) headers["content-type"] = "application/json";
  if (options.rawBody !== undefined) headers["content-type"] ??= options.rawBody.type || "application/octet-stream";
  if (options.version !== undefined) headers["if-match"] = `W/"${options.version}"`;
  return fetch(buildUrl(path, options.query), {
    method: options.method ?? (options.body === undefined && options.rawBody === undefined ? "GET" : "POST"),
    headers,
    body: options.rawBody ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
    credentials: "include",
    signal: options.signal,
  });
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);
  if (response.status === 401 && !path.startsWith("/v1/auth/login") && (await refreshSession())) {
    response = await send(path, options);
  }
  if (!response.ok) {
    let body: Record<string, unknown>;
    try {
      body = (await response.json()) as Record<string, unknown>;
    } catch {
      body = { detail: response.statusText };
    }
    throw new ApiError(response.status, body);
  }
  if (options.raw) return response as unknown as T;
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** The file name the server suggests in Content-Disposition, if it's a safe one. */
export function suggestedName(header: string | null): string | null {
  // Prefer the UTF-8 name (Bangla file names), then the plain one. Never a path.
  const encoded = header?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      const name = decodeURIComponent(encoded.trim());
      if (name && !/[/\\]/.test(name) && name !== "." && name !== "..") return name;
    } catch {
      // fall through to the plain name
    }
  }
  const match = header?.match(/filename="([^"/\\]+)"/);
  return match?.[1] ?? null;
}

/** Download a file from the API (e.g. CSV export) with the current credentials. The
 * server's file name wins over `filename`, which is the fallback. */
export async function download(path: string, query: RequestOptions["query"], filename: string): Promise<void> {
  const response = await api<Response>(path, { query, raw: true });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = suggestedName(response.headers.get("content-disposition")) ?? filename;
  link.click();
  URL.revokeObjectURL(url);
}
