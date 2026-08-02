export interface HealthResponse {
  status: "ok";
  service: string;
  environment: string;
}

export type HealthResult =
  | { kind: "available"; health: HealthResponse }
  | { kind: "unavailable"; message: string };

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    candidate.status === "ok" &&
    typeof candidate.service === "string" &&
    typeof candidate.environment === "string"
  );
}

export async function getBackendHealth(): Promise<HealthResult> {
  const apiBaseUrl = (process.env.API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(3_000),
    });

    if (!response.ok) {
      return {
        kind: "unavailable",
        message: `Backend returned HTTP ${response.status}.`,
      };
    }

    const payload: unknown = await response.json();
    if (!isHealthResponse(payload)) {
      return {
        kind: "unavailable",
        message: "Backend returned an unexpected health response.",
      };
    }

    return { kind: "available", health: payload };
  } catch {
    return {
      kind: "unavailable",
      message: "Backend health endpoint is currently unreachable.",
    };
  }
}
