"use client";

import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Frontend route error", { digest: error.digest });
  }, [error]);

  return (
    <main className="shell page-main">
      <section className="error-card" role="alert">
        <p className="eyebrow">Application error</p>
        <h1>Something went wrong.</h1>
        <p>The page could not be loaded. No internal error details were exposed.</p>
        <button type="button" onClick={reset}>
          Try again
        </button>
      </section>
    </main>
  );
}
