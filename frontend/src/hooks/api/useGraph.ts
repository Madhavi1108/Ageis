import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../../services/apiClient";
import { qk } from "../../services/queryKeys";
import type { CodeGraphSummary, NodeDetail, SubgraphResult } from "../../types/api";

function base(repoId: string, snapshotId: string): string {
  return `/repositories/${repoId}/snapshots/${snapshotId}/analysis/graph`;
}

export function useGraphSummary(repoId?: string, snapshotId?: string) {
  return useQuery({
    queryKey: qk.graphSummary(repoId ?? "", snapshotId ?? ""),
    enabled: !!repoId && !!snapshotId,
    retry: false,
    queryFn: ({ signal }) => apiGet<CodeGraphSummary>(base(repoId!, snapshotId!), { signal }),
  });
}

export function useSubgraph(
  repoId: string | undefined,
  snapshotId: string | undefined,
  node: string | undefined,
  hops: number,
  opts?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: qk.subgraph(repoId ?? "", snapshotId ?? "", node ?? "", hops),
    enabled: !!repoId && !!snapshotId && !!node && (opts?.enabled ?? true),
    retry: false,
    queryFn: ({ signal }) =>
      apiGet<SubgraphResult>(`${base(repoId!, snapshotId!)}/subgraph`, {
        signal,
        query: { node, hops },
      }),
  });
}

export function useGraphNode(
  repoId: string | undefined,
  snapshotId: string | undefined,
  nodeId: string | undefined,
) {
  return useQuery({
    queryKey: qk.graphNode(repoId ?? "", snapshotId ?? "", nodeId ?? ""),
    enabled: !!repoId && !!snapshotId && !!nodeId,
    retry: false,
    queryFn: ({ signal }) =>
      apiGet<NodeDetail>(`${base(repoId!, snapshotId!)}/node/${nodeId}`, { signal }),
  });
}
