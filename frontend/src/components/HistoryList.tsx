import { ChevronRight, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { formatPeriod } from "../lib/formatters";

export interface ReportListItem {
  report_id: string;
  period: string;
  generated_at: string | null;
  anomaly_count: number;
  error_count: number;
}

interface HistoryListProps {
  reports: ReportListItem[];
  loading?: boolean;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function anomalyText(n: number): string {
  if (n === 0) return "No anomalies";
  return `${n} ${n === 1 ? "anomaly" : "anomalies"}`;
}

/**
 * Report history list — one row per verified report. Click → /report/:period.
 * Desktop and tablet: same layout. Hidden on mobile (Dashboard itself is hidden
 * on mobile per docs/design.md §Responsive).
 */
export function HistoryList({ reports, loading }: HistoryListProps) {
  if (loading) {
    return (
      <div
        className="rounded-lg border border-border bg-surface"
        aria-label="Loading recent reports"
      >
        <div className="divide-y divide-border">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="px-4 py-3 flex items-center justify-between animate-pulse"
            >
              <div className="space-y-1.5">
                <div className="h-4 w-40 bg-severity-normal-bg rounded" />
                <div className="h-3 w-56 bg-severity-normal-bg rounded" />
              </div>
              <div className="h-4 w-4 bg-severity-normal-bg rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <FileText
          className="h-8 w-8 text-text-secondary mx-auto mb-2 opacity-60"
          aria-hidden
        />
        <p className="text-sm font-medium text-text-primary">No reports yet</p>
        <p className="text-sm text-text-secondary mt-1">
          Upload your first period to see analysis here.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <ul className="divide-y divide-border" aria-label="Recent reports">
        {reports.map((r) => (
          <li key={r.report_id}>
            <Link
              to={`/report/${r.period}`}
              className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-canvas transition-colors focus:outline-none focus:bg-canvas focus:ring-2 focus:ring-accent focus:ring-inset"
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-text-primary">
                  {formatPeriod(r.period)}
                </div>
                <div className="text-xs text-text-secondary mt-0.5">
                  {anomalyText(r.anomaly_count)}
                  <span className="mx-1.5">·</span>
                  Generated {formatDate(r.generated_at)}
                </div>
              </div>
              <ChevronRight
                className="h-4 w-4 text-text-secondary shrink-0"
                aria-hidden
              />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
