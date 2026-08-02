import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthStatus } from "@/components/health-status";

describe("HealthStatus", () => {
  it("renders backend health details when the service is available", () => {
    render(
      <HealthStatus
        result={{
          kind: "available",
          health: {
            status: "ok",
            service: "ai-video-os-api",
            environment: "test",
          },
        }}
      />,
    );

    expect(screen.getByText("Operational")).toBeInTheDocument();
    expect(screen.getByText("ai-video-os-api")).toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();
  });

  it("renders a safe unavailable state", () => {
    render(
      <HealthStatus result={{ kind: "unavailable", message: "Backend is unavailable." }} />,
    );

    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Backend is unavailable.");
  });
});
