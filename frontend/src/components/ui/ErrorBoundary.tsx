import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught application error:", error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleHome = () => {
    window.location.href = "/";
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-kfl-canvas flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-kfl-surface rounded-xl shadow-lg border border-kfl-border p-8 text-center">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-kfl-status-warning-bg text-kfl-status-warning mb-5">
              <AlertTriangle size={28} />
            </div>
            <h1 className="text-xl font-bold text-kfl-text tracking-tight mb-2">
              Application Error
            </h1>
            <p className="text-sm text-kfl-secondary mb-6 leading-relaxed">
              An unexpected error occurred while rendering this page. The issue has been logged to the browser console.
            </p>
            {this.state.error?.message && (
              <div className="mb-6 p-3 bg-kfl-surface-subtle rounded text-xs text-left font-mono text-kfl-secondary overflow-x-auto max-h-32">
                {this.state.error.message}
              </div>
            )}
            <div className="flex gap-3 justify-center">
              <button
                type="button"
                onClick={this.handleReload}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-primary-foreground bg-primary hover:bg-primary/90 transition"
              >
                <RefreshCw size={15} />
                Reload Page
              </button>
              <button
                type="button"
                onClick={this.handleHome}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-secondary-foreground bg-secondary hover:bg-secondary/80 transition"
              >
                <Home size={15} />
                Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
