import { useState } from "react";

import { useHealth, useVersion } from "../hooks/api/useSystem";
import { useSettings } from "../hooks/useSettings";
import { getBaseUrl } from "../services/apiClient";
import { DEFAULT_SETTINGS } from "../services/settingsStore";
import { Badge } from "../components/primitives/Badge";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { SelectField, TextField } from "../components/primitives/Field";
import { useToast } from "../components/feedback/Toast";

export function SettingsPage() {
  const { settings, update } = useSettings();
  const { notify } = useToast();
  const health = useHealth();
  const version = useVersion();

  const [apiBaseUrl, setApiBaseUrl] = useState(settings.apiBaseUrl ?? "");
  const [apiKey, setApiKey] = useState("");
  const [actorName, setActorName] = useState(settings.actorName ?? "");

  const maskedKey = settings.apiKey
    ? `••••${settings.apiKey.slice(-4)}`
    : "none";

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-lg font-semibold">System settings</h1>
      <p className="text-xs text-muted">
        These preferences live in your browser only. Providers, policies, and limits are managed on
        the backend and are not configurable here.
      </p>

      <Card>
        <CardHeader title="API connection" subtitle={`effective: ${getBaseUrl()}`} />
        <CardBody className="space-y-3">
          <TextField
            label="API base URL override"
            value={apiBaseUrl}
            onChange={(e) => setApiBaseUrl(e.target.value)}
            placeholder={DEFAULT_SETTINGS.apiBaseUrl ?? "http://localhost:8000"}
            className="font-mono"
          />
          <div className="flex items-end gap-2">
            <TextField
              label={`API key (current: ${maskedKey})`}
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="paste to set a new key"
            />
            <Button variant="ghost" onClick={() => update({ apiKey: null })}>
              Clear key
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => {
                update({
                  apiBaseUrl: apiBaseUrl.trim() || null,
                  ...(apiKey ? { apiKey } : {}),
                });
                setApiKey("");
                notify("Connection settings saved", "success");
              }}
            >
              Save
            </Button>
            <Button variant="secondary" onClick={() => health.refetch()}>
              Test connection
            </Button>
            {health.isSuccess ? (
              <Badge tone="success">reachable</Badge>
            ) : health.isError ? (
              <Badge tone="danger">unreachable</Badge>
            ) : null}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Actor" />
        <CardBody>
          <div className="flex items-end gap-2">
            <TextField
              label="Your name (prefills task author + HITL decisions)"
              value={actorName}
              onChange={(e) => setActorName(e.target.value)}
            />
            <Button
              onClick={() => {
                update({ actorName: actorName.trim() || null });
                notify("Saved", "success");
              }}
            >
              Save
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Display & polling" />
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label="Theme"
            value={settings.theme}
            onChange={(e) =>
              update({ theme: e.target.value as "light" | "dark" | "system" })
            }
          >
            <option value="system">system</option>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </SelectField>
          <TextField
            label="Poll interval (ms)"
            type="number"
            min={500}
            value={settings.pollBaseMs}
            onChange={(e) => update({ pollBaseMs: Math.max(500, Number(e.target.value) || 2000) })}
          />
          <TextField
            label="Graph node cap"
            type="number"
            min={20}
            value={settings.graphNodeCap}
            onChange={(e) => update({ graphNodeCap: Math.max(20, Number(e.target.value) || 300) })}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Backend build (read-only)" />
        <CardBody className="text-sm">
          {version.data ? (
            <p>
              v{version.data.version}{" "}
              <span className="text-muted">({version.data.git_sha ?? "unknown"})</span>
            </p>
          ) : (
            <p className="text-muted">unknown</p>
          )}
          <p className="text-xs text-muted">
            health: {health.data ? String(health.data.status ?? "ok") : "unknown"}
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
