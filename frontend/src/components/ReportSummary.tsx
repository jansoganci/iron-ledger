import { AlertTriangle, CheckCircle, Download, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { formatPeriod } from "../lib/formatters";
import { ReconciliationPanel } from "./ReconciliationPanel";
import type { ReconciliationItem } from "./ReconciliationCard";

export type ReportStatus = "verified" | "stale" | "guardrail_failed";
export type OpusStatus = "pending" | "running" | "done" | "failed";

interface ReportSummaryProps {
  summary: string;
  period: string;
  generatedAt: string | null;
  anomalyCount: number;
  companyName: string;
  status: ReportStatus;
  isGenerating?: boolean;
  opusStatus?: OpusStatus | null;
  opusUpgraded?: boolean;
  onRegenerate?: () => void;
  reconciliations?: ReconciliationItem[] | null;
  excelDownloadUrl?: string;
}

export function ReportSummary({
  summary,
  period,
  generatedAt,
  anomalyCount,
  companyName,
  status,
  isGenerating = false,
  opusStatus = null,
  opusUpgraded = false,
  onRegenerate,
  reconciliations,
  excelDownloadUrl,
}: ReportSummaryProps) {
  const periodLabel = formatPeriod(period);

  // guardrail_failed: GuardrailWarning takes over the screen — render nothing.
  if (status === "guardrail_failed") {
    return null;
  }

  if (isGenerating) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-text-primary">
                {periodLabel} — {companyName}
              </h1>
              <Loader2 className="h-4 w-4 text-accent animate-spin" aria-label="Generating" />
            </div>
            <p className="text-sm text-text-secondary mt-0.5">Generating verified report…</p>
          </div>
        </div>

        {/* Skeleton paragraphs */}
        <div className="space-y-2 animate-pulse">
          <div className="h-3 bg-severity-normal-bg rounded w-[90%]" />
          <div className="h-3 bg-severity-normal-bg rounded w-[90%]" />
          <div className="h-3 bg-severity-normal-bg rounded w-[70%]" />
          <div className="h-3 bg-severity-normal-bg rounded w-[50%]" />
        </div>
      </div>
    );
  }

  const isStale = status === "stale";
  const showOpusBanner = opusStatus === "pending" || opusStatus === "running";

  return (
    <div className="rounded-lg border border-border bg-surface p-6 space-y-4">
      {showOpusBanner && (
        <div
          className="flex items-center gap-2 rounded-md bg-accent/10 border border-accent/20 px-3 py-2 text-sm text-accent"
          style={{ transition: "opacity 0.4s ease" }}
        >
          <Loader2 className="h-4 w-4 animate-spin shrink-0" aria-hidden />
          <span>Advanced analysis in progress — your upgraded report will appear here shortly.</span>
        </div>
      )}
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-semibold text-text-primary">
            {periodLabel} — {companyName}
          </h1>
          {status === "verified" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-favorable-bg text-favorable-fg px-2 py-0.5 text-xs font-semibold">
              <CheckCircle className="h-3 w-3" aria-hidden />
              Verified · Guardrail Passed
            </span>
          )}
          {opusUpgraded && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent/10 text-accent px-2 py-0.5 text-xs font-semibold">
              <Sparkles className="h-3 w-3" aria-hidden />
              Advanced Analysis
            </span>
          )}
          {isStale && (
            <span className="inline-flex items-center gap-1 rounded-full bg-severity-medium-bg text-severity-medium-fg px-2 py-0.5 text-xs font-semibold">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              Out of date
            </span>
          )}
        </div>

        {anomalyCount > 0 && (
          <p className="text-sm text-text-secondary mt-1">
            {anomalyCount} item{anomalyCount !== 1 ? "s" : ""} flagged
          </p>
        )}

        {generatedAt && (
          <p className="text-xs text-text-secondary mt-0.5">
            Generated {new Date(generatedAt).toLocaleString("en-US")}
          </p>
        )}
      </div>

      {isStale && (
        <div className="rounded-md bg-severity-medium-bg text-severity-medium-fg px-3 py-2 text-sm flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden />
          <p className="flex-1">
            This report was generated before you re-uploaded the source file.{" "}
            {onRegenerate ? (
              <button
                type="button"
                onClick={onRegenerate}
                className="inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:no-underline focus:outline-none focus:ring-2 focus:ring-severity-medium-fg rounded"
              >
                <RefreshCw className="h-3 w-3" aria-hidden />
                Regenerate report
              </button>
            ) : (
              <span className="font-medium">Regenerate report.</span>
            )}
          </p>
        </div>
      )}

      {/* Narrative prose from Claude — numbers inside anomaly cards carry provenance */}
      <div className="prose prose-sm max-w-none text-text-primary leading-relaxed whitespace-pre-wrap">
        {summary}
      </div>

      {/* Reconciliation findings — above anomaly cards in page flow */}
      <ReconciliationPanel reconciliations={reconciliations} />

      {/* Download Excel */}
      {excelDownloadUrl && (
        <div className="flex justify-end">
          <a
            href={excelDownloadUrl}
            download
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <Download className="h-4 w-4" aria-hidden />
            Download Excel
          </a>
        </div>
      )}
    </div>
  );
}
