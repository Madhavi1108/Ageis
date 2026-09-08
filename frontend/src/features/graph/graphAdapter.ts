import type { NodeDetail, NodeRef, SubgraphResult } from "../../types/api";

export interface CyElement {
  data: {
    id: string;
    label?: string;
    nodeType?: string;
    ref?: string;
    source?: string;
    target?: string;
    edgeType?: string;
    confidence?: string | null;
  };
}

export interface GraphModel {
  elements: CyElement[];
  nodeIds: Set<string>;
  truncated: boolean;
  nodeCount: number;
}

function nodeEl(n: NodeRef): CyElement {
  return { data: { id: n.id, label: n.label || n.ref, nodeType: n.node_type, ref: n.ref } };
}

export function subgraphToModel(sub: SubgraphResult, cap: number): GraphModel {
  const model: GraphModel = { elements: [], nodeIds: new Set(), truncated: false, nodeCount: 0 };
  addNodes(model, [sub.center, ...sub.nodes], cap);
  addEdges(model, sub.edges);
  return model;
}

/** Merge a fresh subgraph into an existing model, de-duplicating by id. */
export function mergeSubgraph(base: GraphModel, sub: SubgraphResult, cap: number): GraphModel {
  const model: GraphModel = {
    elements: [...base.elements],
    nodeIds: new Set(base.nodeIds),
    truncated: base.truncated,
    nodeCount: base.nodeCount,
  };
  addNodes(model, [sub.center, ...sub.nodes], cap);
  addEdges(model, sub.edges);
  return model;
}

function addNodes(model: GraphModel, nodes: NodeRef[], cap: number): void {
  for (const n of nodes) {
    if (model.nodeIds.has(n.id)) continue;
    if (model.nodeCount >= cap) {
      model.truncated = true;
      continue;
    }
    model.nodeIds.add(n.id);
    model.nodeCount += 1;
    model.elements.push(nodeEl(n));
  }
}

function addEdges(model: GraphModel, edges: SubgraphResult["edges"]): void {
  const seen = new Set(
    model.elements.filter((e) => e.data.source).map((e) => e.data.id),
  );
  for (const e of edges) {
    if (!model.nodeIds.has(e.source.id) || !model.nodeIds.has(e.target.id)) continue;
    const id = e.id || `${e.source.id}->${e.target.id}:${e.edge_type}`;
    if (seen.has(id)) continue;
    seen.add(id);
    model.elements.push({
      data: {
        id,
        source: e.source.id,
        target: e.target.id,
        edgeType: e.edge_type,
        confidence: e.confidence ?? null,
      },
    });
  }
}

export function nodeDetailEdges(detail: NodeDetail): { in: number; out: number } {
  return { in: detail.incoming.length, out: detail.outgoing.length };
}
