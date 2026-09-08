import { useHealth, useVersion } from "../hooks/api/useSystem";
import { getBaseUrl } from "../services/apiClient";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { Badge } from "../components/primitives/Badge";
import { InlineSpinner } from "../components/feedback/LoadingBlock";

export function HealthPage() {
  const health = useHealth();
  const version = useVersion();

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-lg font-semibold">System health</h1>
      <Card>
        <CardHeader title="API" subtitle={getBaseUrl()} />
        <CardBody>
          {health.isLoading ? (
            <InlineSpinner label="Checking…" />
          ) : health.isError ? (
            <Badge tone="danger">unreachable</Badge>
          ) : (
            <Badge tone="success">status: {String(health.data?.status ?? "ok")}</Badge>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Build" />
        <CardBody className="text-sm">
          {version.data ? (
            <p>
              v{version.data.version}{" "}
              <span className="text-muted">({version.data.git_sha ?? "unknown"})</span>
            </p>
          ) : (
            <InlineSpinner />
          )}
        </CardBody>
      </Card>
    </div>
  );
}
