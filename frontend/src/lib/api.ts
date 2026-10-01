import { CLIENT_MESSAGES } from "./messages";
import { supabase } from "./supabase";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    message?: string,
    public traceId?: string
  ) {
    super(message ?? `API ${status}`);
    this.name = "ApiError";
  }
}

export class UnauthorizedError extends ApiError {
  constructor(body: unknown, traceId?: string) {
    super(401, body, CLIENT_MESSAGES.SESSION_EXPIRED, traceId);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends ApiError {
  constructor(body: unknown, traceId?: string) {
    super(403, body, CLIENT_MESSAGES.FORBIDDEN, traceId);
    this.name = "ForbiddenError";
  }
}

export class RateLimitedError extends ApiError {
  constructor(
    public retryAfterSeconds: number,
    body: unknown,
    traceId?: string
  ) {
    super(429, body, CLIENT_MESSAGES.RATE_LIMITED, traceId);
    this.name = "RateLimitedError";
  }
}

export class ServerError extends ApiError {
  constructor(status: number, body: unknown, traceId?: string) {
    super(status, body, CLIENT_MESSAGES.UNKNOWN_ERROR, traceId);
    this.name = "ServerError";
  }
}

type FetchOptions = Omit<RequestInit, "body"> & {
  json?: unknown;
  body?: RequestInit["body"];
};

export interface BlobDownload {
  blob: Blob;
  filename: string | null;
}

function filenameFromContentDisposition(header: string | null): string | null {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      return utf8[1];
    }
  }
  const quoted = /filename="([^"]+)"/i.exec(header);
  if (quoted) return quoted[1];
  const plain = /filename=([^;]+)/i.exec(header);
  return plain ? plain[1].trim() : null;
}

async function authorizedResponse(
  path: string,
  opts: FetchOptions = {}
): Promise<Response> {
  const { data: sessionData } = await supabase.auth.getSession();
  const token = sessionData.session?.access_token;

  const headers = new Headers(opts.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let body: RequestInit["body"] = opts.body;
  if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(opts.json);
  }

  try {
    return await fetch(`${BASE_URL}${path}`, { ...opts, headers, body });
  } catch {
    throw new ApiError(0, null, CLIENT_MESSAGES.NETWORK_ERROR);
  }
}

function parseBody(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function throwForErrorStatus(res: Response, parsed: unknown): Promise<never> {
  const traceId =
    res.headers.get("X-Trace-Id") ??
    res.headers.get("x-trace-id") ??
    undefined;

  if (traceId) {
    // eslint-disable-next-line no-console
    console.error(`[API ${res.status}] trace_id=${traceId}`, parsed);
  }

  if (res.status === 401) {
    await supabase.auth.signOut();
    if (!window.location.pathname.startsWith("/login")) {
      const next = encodeURIComponent(
        window.location.pathname + window.location.search
      );
      window.location.href = `/login?next=${next}`;
    }
    throw new UnauthorizedError(parsed, traceId);
  }
  if (res.status === 403) throw new ForbiddenError(parsed, traceId);
  if (res.status === 429) {
    const retryAfter = Number(res.headers.get("Retry-After") ?? 60);
    throw new RateLimitedError(retryAfter, parsed, traceId);
  }
  if (res.status >= 500) throw new ServerError(res.status, parsed, traceId);
  throw new ApiError(res.status, parsed, undefined, traceId);
}

export function apiErrorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const detail = (err.body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  if (err instanceof ApiError && err.message && !err.message.startsWith("API ")) {
    return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

/** Centralized fetch with JWT attach + 401/403/429/5xx dispatch + trace_id logging. */
export async function apiFetch<T>(
  path: string,
  opts: FetchOptions = {}
): Promise<T> {
  const res = await authorizedResponse(path, opts);
  const parsed = parseBody(await res.text());
  if (res.ok) return parsed as T;
  return throwForErrorStatus(res, parsed);
}

/** Same auth and error handling as apiFetch, for binary downloads. */
export async function apiFetchBlob(
  path: string,
  opts: FetchOptions = {}
): Promise<BlobDownload> {
  const res = await authorizedResponse(path, opts);
  if (res.ok) {
    return {
      blob: await res.blob(),
      filename: filenameFromContentDisposition(
        res.headers.get("Content-Disposition")
      ),
    };
  }
  const parsed = parseBody(await res.text());
  return throwForErrorStatus(res, parsed);
}
