import { describe, expect, it } from "vitest";

import { subgraph } from "../../test/fixtures";
import { mergeSubgraph, subgraphToModel } from "./graphAdapter";

describe("graphAdapter", () => {
  it("converts a subgraph into cytoscape elements (nodes + edges)", () => {
    const model = subgraphToModel(subgraph, 300);
    const nodes = model.elements.filter((e) => !e.data.source);
    const edges = model.elements.filter((e) => e.data.source);
    expect(nodes).toHaveLength(3); // center + 2
    expect(edges).toHaveLength(2);
    expect(model.truncated).toBe(false);
  });

  it("de-duplicates nodes and edges when merging the same subgraph twice", () => {
    const a = subgraphToModel(subgraph, 300);
    const b = mergeSubgraph(a, subgraph, 300);
    expect(b.nodeCount).toBe(a.nodeCount);
    expect(b.elements.length).toBe(a.elements.length);
  });

  it("enforces the node cap and flags truncation", () => {
    const model = subgraphToModel(subgraph, 2);
    expect(model.nodeCount).toBe(2);
    expect(model.truncated).toBe(true);
    // edges to the dropped node are not added
    expect(model.elements.filter((e) => e.data.source).length).toBeLessThanOrEqual(1);
  });
});
