import { HealthStatus } from "@/components/health-status";
import { getBackendHealth } from "@/lib/api-client";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await getBackendHealth();

  return (
    <main className="shell page-main">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Operator interface</p>
        <h1 id="page-title">Development environment</h1>
        <p className="hero__summary">
          The frontend foundation is running and ready to connect to the AI Video OS backend.
        </p>
      </section>
      <HealthStatus result={health} />
    </main>
  );
}
