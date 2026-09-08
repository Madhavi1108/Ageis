// Minimal type shims for graph libs that don't ship their own .d.ts.

declare module "cytoscape" {
  interface CytoscapeStatic {
    (opts?: unknown): unknown;
    use: (ext: unknown) => void;
  }
  const cytoscape: CytoscapeStatic;
  export default cytoscape;
}

declare module "cytoscape-fcose" {
  const ext: unknown;
  export default ext;
}

declare module "react-cytoscapejs" {
  import type { CSSProperties } from "react";

  export interface CytoscapeComponentProps {
    elements: unknown[];
    style?: CSSProperties;
    className?: string;
    layout?: Record<string, unknown>;
    stylesheet?: unknown[];
    cy?: (cy: cytoscapeCoreLike) => void;
    minZoom?: number;
    maxZoom?: number;
    wheelSensitivity?: number;
  }

  export interface cytoscapeCoreLike {
    on: (evt: string, selector: string, handler: (e: { target: unknown }) => void) => void;
    layout: (opts: Record<string, unknown>) => { run: () => void };
    fit: () => void;
    elements: () => unknown;
    destroy: () => void;
  }

  const CytoscapeComponent: (props: CytoscapeComponentProps) => JSX.Element;
  export default CytoscapeComponent;
}
