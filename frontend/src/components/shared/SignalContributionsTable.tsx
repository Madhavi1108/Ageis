import type { SignalContribution } from "../../types/api";
import { pct } from "../../lib/format";
import { Badge } from "../primitives/Badge";
import { Table, TD, TH, THead, TR } from "../primitives/Table";

export function SignalContributionsTable({ signals }: { signals: SignalContribution[] }) {
  if (!signals.length) return <p className="text-xs text-muted">No signal breakdown.</p>;
  return (
    <Table>
      <THead>
        <TR>
          <TH>Signal</TH>
          <TH>Normalized</TH>
          <TH>Weight</TH>
          <TH>Contribution</TH>
          <TH>Basis</TH>
        </TR>
      </THead>
      <tbody>
        {signals.map((s) => (
          <TR key={s.name}>
            <TD>
              <div>{s.name}</div>
              {s.unavailable_reason ? (
                <div className="text-[11px] text-muted">{s.unavailable_reason}</div>
              ) : null}
            </TD>
            <TD>{s.normalized.toFixed(2)}</TD>
            <TD>{pct(s.weight)}</TD>
            <TD>{s.contribution.toFixed(3)}</TD>
            <TD>
              <Badge tone={s.basis === "FACT" ? "success" : "neutral"}>{s.basis}</Badge>
            </TD>
          </TR>
        ))}
      </tbody>
    </Table>
  );
}
