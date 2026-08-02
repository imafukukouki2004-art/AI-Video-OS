import type { HealthResult } from "@/lib/api-client";

interface HealthStatusProps {
  result: HealthResult;
}

export function HealthStatus({ result }: HealthStatusProps) {
  const available = result.kind === "available";

  return (
    <section aria-labelledby="backend-status-heading" className="status-card">
      <div className="status-card__header">
        <div>
          <p className="eyebrow">System status</p>
          <h2 id="backend-status-heading">Backend API</h2>
        </div>
        <span className={available ? "status-pill status-pill--ok" : "status-pill status-pill--error"}>
          <span aria-hidden="true" className="status-pill__dot" />
          {available ? "Operational" : "Unavailable"}
        </span>
      </div>

      {available ? (
        <dl className="status-details">
          <div>
            <dt>Service</dt>
            <dd>{result.health.service}</dd>
          </div>
          <div>
            <dt>Environment</dt>
            <dd>{result.health.environment}</dd>
          </div>
          <div>
            <dt>Health</dt>
            <dd>{result.health.status}</dd>
          </div>
        </dl>
      ) : (
        <p className="status-message" role="status">
          {result.message}
        </p>
      )}
    </section>
  );
}
