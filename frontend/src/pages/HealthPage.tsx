import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../services/apiClient";
import type { HealthResponse, VersionResponse } from "../types/api";

export function HealthPage() {
  const health = useQuery({
    queryKey: ["healthz"],
    queryFn: () => apiGet<HealthResponse>("/healthz"),
  });
  const version = useQuery({
    queryKey: ["version"],
    queryFn: () => apiGet<VersionResponse>("/version"),
  });

  return (
    <main>
      <h1>AEGIS</h1>
      <section>
        <h2>API health</h2>
        {health.isLoading && <p>Checking...</p>}
        {health.isError && <p>Unreachable: {(health.error as Error).message}</p>}
        {health.data && <p>Status: {health.data.status}</p>}
      </section>
      <section>
        <h2>Build</h2>
        {version.data && (
          <p>
            v{version.data.version} ({version.data.git_sha ?? "unknown"})
          </p>
        )}
      </section>
    </main>
  );
}
