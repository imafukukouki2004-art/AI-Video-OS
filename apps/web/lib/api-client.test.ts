import { afterEach, describe, expect, it, vi } from "vitest";

import { getBackendHealth } from "@/lib/api-client";

describe("getBackendHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns validated health data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          service: "ai-video-os-api",
          environment: "test",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getBackendHealth()).resolves.toEqual({
      kind: "available",
      health: {
        status: "ok",
        service: "ai-video-os-api",
        environment: "test",
      },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("returns an unavailable result for a failed request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

    await expect(getBackendHealth()).resolves.toEqual({
      kind: "unavailable",
      message: "Backend health endpoint is currently unreachable.",
    });
  });

  it("rejects an unexpected health response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "unknown" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(getBackendHealth()).resolves.toEqual({
      kind: "unavailable",
      message: "Backend returned an unexpected health response.",
    });
  });
});
