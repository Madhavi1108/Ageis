import { useEffect, useMemo, useRef } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import CytoscapeComponent from "react-cytoscapejs";

import type { GraphModel } from "./graphAdapter";

let registered = false;
if (!registered) {
  try {
    cytoscape.use(fcose);
    registered = true;
  } catch {
    /* already registered / test env */
  }
}

const STYLESHEET = [
  {
    selector: "node",
    style: {
      "background-color": "#3b82f6",
      label: "data(label)",
      "font-size": 9,
      color: "#94a3b8",
      "text-valign": "bottom",
      "text-halign": "center",
      width: 14,
      height: 14,
    },
  },
  {
    selector: 'node[nodeType = "test"]',
    style: { "background-color": "#16a34a" },
  },
  {
    selector: 'node[nodeType = "file"]',
    style: { "background-color": "#a855f7" },
  },
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "#64748b",
      "target-arrow-color": "#64748b",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      opacity: 0.6,
    },
  },
  {
    selector: ":selected",
    style: { "background-color": "#f59e0b", "line-color": "#f59e0b" },
  },
];

export function GraphCanvas({
  model,
  onNodeSelect,
  onNodeExpand,
}: {
  model: GraphModel;
  onNodeSelect: (id: string) => void;
  onNodeExpand: (id: string) => void;
}) {
  const cyRef = useRef<{ layout: (o: Record<string, unknown>) => { run: () => void } } | null>(null);
  const elements = useMemo(() => model.elements.map((e) => ({ ...e })), [model.elements]);

  useEffect(() => {
    cyRef.current?.layout({ name: "fcose", animate: false, quality: "default" }).run();
  }, [elements.length]);

  return (
    <div className="relative h-[520px] w-full overflow-hidden rounded-lg border border-border bg-surface">
      {model.truncated ? (
        <div className="absolute left-2 top-2 z-10 rounded bg-awaiting/20 px-2 py-1 text-[11px] text-awaiting">
          graph truncated — {model.nodeCount} nodes shown
        </div>
      ) : null}
      <CytoscapeComponent
        elements={elements}
        stylesheet={STYLESHEET}
        style={{ width: "100%", height: "100%" }}
        layout={{ name: "fcose", animate: false }}
        wheelSensitivity={0.2}
        cy={(cy) => {
          cyRef.current = cy as unknown as typeof cyRef.current;
          cy.on("tap", "node", (evt: { target: unknown }) => {
            const id = (evt.target as { id: () => string }).id();
            onNodeSelect(id);
          });
          cy.on("dbltap", "node", (evt: { target: unknown }) => {
            const id = (evt.target as { id: () => string }).id();
            onNodeExpand(id);
          });
        }}
      />
    </div>
  );
}
