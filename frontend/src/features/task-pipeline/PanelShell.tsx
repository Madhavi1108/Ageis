import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { EmptyState } from "../../components/feedback/EmptyState";
import { InlineSpinner } from "../../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../../services/errorMessages";

/**
 * Renders the shared loading / not-produced-yet / error framing for a stage
 * panel; when data is present, calls `children`.
 */
export function PanelShell<T>({
  query,
  notReady = "Not produced for this task yet.",
  children,
}: {
  query: UseQueryResult<T>;
  notReady?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isLoading) return <InlineSpinner label="Loading stage…" />;
  if (query.isError) {
    if (isStageNotReady(query.error)) {
      return <EmptyState title={notReady} />;
    }
    return <ErrorEnvelopeAlert error={query.error} />;
  }
  if (query.data == null) return <EmptyState title={notReady} />;
  return <>{children(query.data)}</>;
}
