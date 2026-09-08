import { useHealth } from "../../hooks/api/useSystem";
import { useSettings } from "../../hooks/useSettings";
import { useTheme } from "../../hooks/useTheme";
import { cn } from "../../lib/cn";
import { Button } from "../primitives/Button";

export function TopBar() {
  const health = useHealth();
  const { resolved, toggle } = useTheme();
  const { settings, update } = useSettings();

  const connected = health.isSuccess;
  const label = health.isLoading ? "checking" : connected ? "connected" : "unreachable";

  return (
    <header className="flex items-center justify-between gap-4 border-b border-border bg-surface px-4 py-2">
      <div className="flex items-center gap-2 text-xs text-muted">
        <span
          className={cn(
            "inline-block h-2 w-2 rounded-full",
            connected ? "bg-done" : health.isLoading ? "bg-pending" : "bg-failed",
          )}
          aria-hidden
        />
        <span>API {label}</span>
      </div>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1.5 text-xs text-muted">
          <input
            type="checkbox"
            checked={settings.livePolling}
            onChange={(e) => update({ livePolling: e.target.checked })}
          />
          Live
        </label>
        <Button size="sm" variant="ghost" onClick={toggle} aria-label="Toggle color theme">
          {resolved === "dark" ? "☾" : "☀"}
        </Button>
      </div>
    </header>
  );
}
