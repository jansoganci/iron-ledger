import React from "react";
import { CLIENT_MESSAGES } from "../lib/messages";

interface State {
  hasError: boolean;
  error?: Error;
}

/**
 * Route-level React error boundary. Catches render and lifecycle exceptions
 * and renders a plain-English fallback instead of a white screen.
 */
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  private handleRefresh = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
          <div className="w-full max-w-md bg-surface border border-border rounded-lg p-6 shadow-sm">
            <h1 className="text-lg font-semibold text-text-primary mb-2">
              Something went wrong
            </h1>
            <p className="text-sm text-text-secondary mb-4">
              {CLIENT_MESSAGES.UNKNOWN_ERROR}
            </p>
            <button
              type="button"
              onClick={this.handleRefresh}
              className="w-full rounded-md bg-accent text-white py-2 px-4 text-sm font-medium hover:opacity-95"
            >
              Refresh
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
