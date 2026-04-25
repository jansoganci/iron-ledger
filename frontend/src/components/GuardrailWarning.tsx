import { AlertTriangle, Download, RefreshCw } from "lucide-react";
import { useState } from "react";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";

interface GuardrailWarningProps {
  runId: string;
  period: string;
  rawDataUrl: string | null;
  errorMessage: string | null;
  onRetry: (newRunId: string) => void;
}

export function GuardrailWarning({
  runId,
  period,
  rawDataUrl,
  errorMessage,
  onRetry,
}: GuardrailWarningProps) {
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  async function handleRetry() {
    setIsRetrying(true);
    setRetryError(null);
    try {
      const res = await apiFetch<{ run_id: string }>(`/runs/${runId}/retry`, {
        method: "POST",
      });
      onRetry(res.run_id);
    } catch (err) {
      setRetryError(
        err instanceof Error ? err.message : "Could not start retry. Please try again."
      );
    } finally {
      setIsRetrying(false);
    }
  }

  const rawUrl = rawDataUrl
    ? `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}${rawDataUrl}`
    : null;

  return (
    <div className="rounded-lg border border-severity-medium-bg bg-surface p-6 space-y-4 max-w-xl mx-auto">
      <div className="flex items-start gap-3">
        <AlertTriangle
          className="h-5 w-5 text-severity-medium-fg mt-0.5 shrink-0"
          aria-hidden
        />
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-text-primary">
            Report Validation Warning
          </h2>
          <p className="text-sm text-text-secondary">
            {errorMessage
              ? errorMessage
              : "We detected a number inconsistency in the generated report. The system tried twice and could not produce a verified report."}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-text-primary">What you can do:</p>
        <div className="space-y-2">
          <button
            onClick={handleRetry}
            disabled={isRetrying}
            className={cn(
              "flex items-center gap-2 w-full justify-center",
              "rounded-md bg-accent px-4 py-2 text-sm font-medium text-white",
              "hover:bg-accent/90 transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
              isRetrying && "opacity-60 cursor-not-allowed"
            )}
          >
            <RefreshCw className={cn("h-4 w-4", isRetrying && "animate-spin")} aria-hidden />
            {isRetrying ? "Starting retry…" : "Retry Analysis"}
          </button>

          {rawUrl && (
            <a
              href={rawUrl}
              download={`raw_${period}_unverified.xlsx`}
              className={cn(
                "flex items-center gap-2 w-full justify-center",
                "rounded-md border border-border px-4 py-2 text-sm text-text-primary",
                "hover:bg-canvas transition-colors"
              )}
            >
              <Download className="h-4 w-4" aria-hidden />
              Download Raw Data (unverified)
            </a>
          )}

          <a
            href="mailto:support@ironledger.app"
            className="block text-center text-sm text-accent hover:underline"
          >
            Contact Support
          </a>
        </div>
      </div>

      {retryError && (
        <div
          role="alert"
          className="rounded-md bg-severity-high-bg text-severity-high-fg px-3 py-2 text-sm"
        >
          {retryError}
        </div>
      )}

    </div>
  );
}
