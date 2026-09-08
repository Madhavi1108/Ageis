import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useGraphNode, useGraphSummary, useSubgraph } from "../hooks/api/useGraph";
import { useSettings } from "../hooks/useSettings";
import { GraphCanvas } from "../features/graph/GraphCanvas";
import { mergeSubgraph, subgraphToModel, type GraphModel } from "../features/graph/graphAdapter";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { TextField } from "../components/primitives/Field";

export function KnowledgeGraphPage() {
  const { repoId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { settings } = useSettings();
  const cap = settings.graphNodeCap;

  const snapshotId = params.get("snapshot") ?? "";
  const [seed, setSeed] = useState(params.get("node") ?? "");
  const [activeNode, setActiveNode] = useState(params.get("node") ?? "");
  const [model, setModel] = useState<GraphModel | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [expandTarget, setExpandTarget] = useState<string | null>(null);

  const summary = useGraphSummary(repoId, snapshotId || undefined);
  const seedGraph = useSubgraph(repoId, snapshotId || undefined, activeNode || undefined, 1, {
    enabled: !!activeNode,
  });
  const expansion = useSubgraph(repoId, snapshotId || undefined, expandTarget || undefined, 1, {
    enabled: !!expandTarget,
  });
  const nodeDetail = useGraphNode(repoId, snapshotId || undefined, selected || undefined);

  useEffect(() => {
    if (seedGraph.data) setModel(subgraphToModel(seedGraph.data, cap));
  }, [seedGraph.data, cap]);

  useEffect(() => {
    if (expansion.data && model) {
      setModel(mergeSubgraph(model, expansion.data, cap));
      setExpandTarget(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expansion.data]);

  const nodesByType = useMemo(
    () => Object.entries(summary.data?.nodes_by_type ?? {}),
    [summary.data],
  );

  if (!snapshotId) {
    return (
      <EmptyState
        title="Pick a snapshot"
        hint="Append ?snapshot=<snapshot_id> (and optionally &node=<ref>) — usually linked from a task's Impact view."
      />
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Repository knowledge graph</h1>

      <Card>
        <CardHeader title="Graph summary" subtitle={`snapshot ${snapshotId}`} />
        <CardBody>
          {summary.isLoading ? (
            <LoadingBlock rows={2} />
          ) : summary.isError && isStageNotReady(summary.error) ? (
            <EmptyState title="No code graph built for this snapshot." />
          ) : summary.isError ? (
            <ErrorEnvelopeAlert error={summary.error} />
          ) : summary.data ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <Badge tone="neutral">{summary.data.node_count} nodes</Badge>
              <Badge tone="neutral">{summary.data.edge_count} edges</Badge>
              <Badge tone="neutral">{summary.data.unresolved_call_count} unresolved calls</Badge>
              {nodesByType.map(([k, v]) => (
                <Badge key={k} tone="neutral">
                  {k}: {v}
                </Badge>
              ))}
            </div>
          ) : null}
        </CardBody>
      </Card>

      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setModel(null);
          setActiveNode(seed.trim());
          setParams((p) => {
            p.set("node", seed.trim());
            p.set("snapshot", snapshotId);
            return p;
          });
        }}
      >
        <TextField
          label="Seed node (path or symbol ref)"
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          className="font-mono"
        />
        <button
          type="submit"
          className="rounded-md bg-accent px-3 py-2 text-sm text-accent-fg"
        >
          Load
        </button>
      </form>

      {seedGraph.isError && !isStageNotReady(seedGraph.error) ? (
        <ErrorEnvelopeAlert error={seedGraph.error} />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        {model ? (
          <GraphCanvas
            model={model}
            onNodeSelect={setSelected}
            onNodeExpand={(id) => setExpandTarget(id)}
          />
        ) : activeNode ? (
          <LoadingBlock rows={8} />
        ) : (
          <EmptyState title="Enter a seed node to render the graph." hint="Double-click a node to expand one hop." />
        )}

        <Card className="h-fit">
          <CardHeader title="Node inspector" />
          <CardBody className="text-xs">
            {!selected ? (
              <p className="text-muted">Select a node to inspect.</p>
            ) : nodeDetail.isLoading ? (
              <LoadingBlock rows={3} />
            ) : nodeDetail.data ? (
              <div className="space-y-2">
                <p className="font-mono">{nodeDetail.data.node.ref}</p>
                <Badge tone="neutral">{nodeDetail.data.node.node_type}</Badge>
                <div>
                  <div className="font-medium">Centrality</div>
                  {Object.entries(nodeDetail.data.centrality).map(([k, v]) => (
                    <div key={k} className="text-muted">
                      {k}: {v.toFixed(3)}
                    </div>
                  ))}
                </div>
                <p className="text-muted">
                  {nodeDetail.data.incoming.length} in · {nodeDetail.data.outgoing.length} out
                </p>
                <button
                  type="button"
                  className="text-accent underline"
                  onClick={() => setExpandTarget(selected)}
                >
                  Expand this node
                </button>
              </div>
            ) : (
              <p className="text-muted">No detail.</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
