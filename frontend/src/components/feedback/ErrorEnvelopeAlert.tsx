import { friendlyMessage, toEnvelope } from "../../services/errorMessages";
import { JsonView } from "../primitives/JsonView";

export function ErrorEnvelopeAlert({ error, className }: { error: unknown; className?: string }) {
  const env = toEnvelope(error);
  return (
    <div
      role="alert"
      className={`rounded-md border border-failed/30 bg-failed/10 px-3 py-2 text-sm text-failed ${className ?? ""}`}
    >
      <p className="font-medium">{friendlyMessage(error)}</p>
      {env ? (
        <p className="mt-1 font-mono text-[11px] opacity-80">{env.code}</p>
      ) : null}
      {env?.details ? (
        <div className="mt-1 text-fg">
          <JsonView value={env.details} label="details" />
        </div>
      ) : null}
      {env?.evidence && env.evidence.length ? (
        <div className="mt-1 text-fg">
          <JsonView value={env.evidence} label="evidence" />
        </div>
      ) : null}
    </div>
  );
}
