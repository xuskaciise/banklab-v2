import type { HealthResponse } from "./types";

export type { HealthResponse };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

// Token from GET /api/auth/csrf. Kept in memory so the frontend also works
// when it runs on a different host than the API (it cannot read the API's
// cookie then). Cleared after login/logout because Django rotates it.
let csrfToken: string | null = null;

async function getCsrfToken(): Promise<string | null> {
  // Same host (local dev): the cookie is readable and always current.
  const fromCookie = readCookie("csrftoken");
  if (fromCookie) return fromCookie;
  if (csrfToken) return csrfToken;
  try {
    const res = await fetch(`${API_URL}/api/auth/csrf`, { credentials: "include" });
    const body = (await res.json()) as { csrf_token?: string };
    csrfToken = body.csrf_token ?? null;
  } catch {
    throw new ApiError("API unreachable");
  }
  return readCookie("csrftoken") ?? csrfToken;
}

const TOKEN_ROTATING_PATHS = new Set([
  "/api/auth/staff-login",
  "/api/auth/student-login",
  "/api/auth/logout",
]);

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * Fetch wrapper for the BankLab API: always sends the session cookie,
 * attaches the CSRF header on unsafe methods (re-reading the cookie each
 * time, since login rotates it) and turns `{detail}` errors into ApiError.
 * Returns undefined for 204 responses.
 */
export async function apiFetch<T>(
  path: string,
  options: Omit<RequestInit, "body"> & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();
  const h = new Headers(headers);
  h.set("Accept", "application/json");
  if (json !== undefined) h.set("Content-Type", "application/json");
  if (!SAFE_METHODS.has(method)) {
    const token = await getCsrfToken();
    if (token) h.set("X-CSRFToken", token);
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      method,
      headers: h,
      credentials: "include",
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch {
    throw new ApiError("API unreachable");
  }
  if (!res.ok) {
    let message = `API error ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") message = body.detail;
    } catch {
      // non-JSON error body
    }
    if (res.status === 403 && message.includes("CSRF")) csrfToken = null;
    throw new ApiError(message, res.status);
  }
  if (TOKEN_ROTATING_PATHS.has(path)) csrfToken = null;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("API unreachable");
  }
  if (!res.ok) throw new ApiError(`API error ${res.status}`, res.status);
  return (await res.json()) as T;
}

export function getHealth() {
  return apiGet<HealthResponse>("/api/health");
}
