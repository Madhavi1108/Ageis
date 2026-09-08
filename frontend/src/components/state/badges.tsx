import { Badge } from "../primitives/Badge";

type Tone = "neutral" | "accent" | "success" | "warn" | "danger";

function toneFor(value: string): Tone {
  const v = value.toUpperCase();
  if (["COMPLETED", "VERIFIED", "PASS", "PASSED", "APPROVED", "HIGH", "DONE"].includes(v)) {
    return "success";
  }
  if (["FAILED", "NOT_VERIFIED", "FAIL", "ERROR", "OOM", "TIMEOUT", "REJECTED", "CRITICAL", "BLOCKED", "VERY_LOW"].includes(v)) {
    return "danger";
  }
  if (["AWAITING_APPROVAL", "PARTIAL", "PARTIALLY_SUPPORTED", "REVISE", "MEDIUM", "CANCELLED", "SKIPPED"].includes(v)) {
    return "warn";
  }
  if (["QUEUED", "PENDING", "LOW", "INFO"].includes(v)) return "neutral";
  return "accent"; // in-progress states
}

export function TaskStateBadge({ state }: { state: string }) {
  return <Badge tone={toneFor(state)}>{state.replace(/_/g, " ")}</Badge>;
}

export function ClassificationBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <Badge tone="neutral">—</Badge>;
  return <Badge tone={toneFor(value)}>{value.replace(/_/g, " ")}</Badge>;
}

const SEV_TONE: Record<string, Tone> = {
  CRITICAL: "danger",
  HIGH: "danger",
  MEDIUM: "warn",
  LOW: "neutral",
  INFO: "neutral",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge tone={SEV_TONE[severity.toUpperCase()] ?? "neutral"}>{severity}</Badge>;
}

export function OutcomeBadge({ outcome }: { outcome: string }) {
  return <Badge tone={toneFor(outcome)}>{outcome}</Badge>;
}
