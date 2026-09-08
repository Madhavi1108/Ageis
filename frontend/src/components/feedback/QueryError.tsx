import { Button } from "../primitives/Button";
import { ErrorEnvelopeAlert } from "./ErrorEnvelopeAlert";

export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="space-y-2">
      <ErrorEnvelopeAlert error={error} />
      {onRetry ? (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
