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

/** Centralized fetch with JWT attach + 401/403/429/5xx dispatch + trace_id logging. */
export async function apiFetch<T>(
  path: string,
  opts: FetchOptions = {}
): Promise<T> {
  const { data: sessionData } = await supabase.auth.getSession();
  const token = sessionData.session?.access_token;

  const headers = new Headers(opts.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let body: RequestInit["body"] = opts.body;
  if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(opts.json);
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...opts, headers, body });
  } catch {
    throw new ApiError(0, null, CLIENT_MESSAGES.NETWORK_ERROR);
  }

  const traceId =
    res.headers.get("X-Trace-Id") ??
    res.headers.get("x-trace-id") ??
    undefined;

  let parsed: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (res.ok) return parsed as T;

  // Always log trace_id on non-2xx for dev debugging
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
