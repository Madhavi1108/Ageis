import type { Evidence } from "../../types/api";
import { Badge } from "../primitives/Badge";

export function EvidenceList({ evidence }: { evidence?: Evidence[] | null }) {
  if (!evidence || evidence.length === 0) return null;
  return (
    <ul className="mt-1 space-y-1">
      {evidence.map((e, i) => (
        <li key={i} className="flex items-start gap-2 text-xs text-muted">
          <Badge tone="neutral">{e.kind}</Badge>
          <span className="font-mono">{e.ref}</span>
          <span>— {e.detail}</span>
        </li>
      ))}
    </ul>
  );
}
