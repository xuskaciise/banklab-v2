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

// TODO: replace with the generated type from schema.d.ts once the backend
// exposes /api/health in its OpenAPI schema.
export type HealthResponse = { status: string };

export function getHealth() {
  return apiGet<HealthResponse>("/api/health");
}
