import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "../primitives/Button";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="m-4 rounded-lg border border-failed/30 bg-failed/10 p-4">
        <p className="text-sm font-semibold text-failed">
          {this.props.fallbackTitle ?? "This view hit an unexpected error."}
        </p>
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-surface-2 p-2 text-xs text-fg">
          {error.message}
        </pre>
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={() => this.setState({ error: null })}>
            Try again
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void navigator.clipboard?.writeText(`${error.message}\n${error.stack ?? ""}`);
            }}
          >
            Copy error
          </Button>
        </div>
      </div>
    );
  }
}
