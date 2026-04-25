import { cn } from "../lib/utils";
import { formatCurrency, formatVariance } from "../lib/formatters";
import { ProvenanceTooltip } from "./ProvenanceTooltip";

export interface AnomalyCardData {
  account: string;
  category: string;
  current: number;
  variance_pct: number | null;
  historical_avg: number;
  direction: "favorable" | "unfavorable" | "neutral";
  severity: "high" | "medium" | "low";
  description: string;
  source_file: string | null;
  source_column: string | null;
}

interface AnomalyCardProps extends AnomalyCardData {}

// Direction drives chip color; severity drives chip label.
// Never color by sign of variance_pct — a negative can be favorable (G&A -34%).
function chipClasses(direction: string, severity: string): string {
  if (direction === "favorable") {
    return "bg-favorable-bg text-favorable-fg";
  }
  if (direction === "neutral") {
    return "bg-severity-normal-bg text-severity-normal-fg";
  }
  // unfavorable — severity determines intensity
  if (severity === "high") return "bg-severity-high-bg text-severity-high-fg";
  if (severity === "medium") return "bg-severity-medium-bg text-severity-medium-fg";
  return "bg-severity-normal-bg text-severity-normal-fg";
}

function severityLabel(severity: string): string {
  if (severity === "high") return "HIGH";
  if (severity === "medium") return "MEDIUM";
  return "NORMAL";
}


export function AnomalyCard({
  account,
  current,
  variance_pct,
  historical_avg,
  direction,
  severity,
  description,
  source_file,
  source_column,
}: AnomalyCardProps) {
  return (
      <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wide">
            {account}
          </h3>
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold",
              chipClasses(direction, severity)
            )}
            aria-label={`Severity: ${severityLabel(severity)}, Direction: ${direction}`}
          >
            {direction === "favorable" && (
              <span aria-hidden className="mr-0.5">▲</span>
            )}
            {direction === "unfavorable" && (
              <span aria-hidden className="mr-0.5">▼</span>
            )}
            {severityLabel(severity)}
          </span>
        </div>

        <div className="flex flex-wrap gap-4 text-sm">
          <div>
            <span className="text-text-secondary text-xs block">This month</span>
            <ProvenanceTooltip sourceFile={source_file} sourceColumn={source_column}>
              {formatCurrency(current)}
            </ProvenanceTooltip>
          </div>
          <div>
            <span className="text-text-secondary text-xs block">Avg.</span>
            <span data-numeric className="text-text-primary">
              {formatCurrency(historical_avg)}
            </span>
          </div>
          <div>
            <span className="text-text-secondary text-xs block">Variance</span>
            <span
              data-numeric
              className={cn(
                "font-medium",
                direction === "favorable" && "text-favorable-fg",
                direction === "unfavorable" && severity === "high" && "text-severity-high-fg",
                direction === "unfavorable" && severity === "medium" && "text-severity-medium-fg",
                direction === "neutral" && "text-text-secondary"
              )}
            >
              {formatVariance(variance_pct)}
            </span>
          </div>
        </div>

        <p className="text-sm text-text-secondary">{description}</p>
      </div>
  );
}

export function AnomalyCardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-3 animate-pulse">
      <div className="flex justify-between">
        <div className="h-4 w-32 bg-severity-normal-bg rounded" />
        <div className="h-5 w-16 bg-severity-normal-bg rounded-full" />
      </div>
      <div className="flex gap-4">
        <div className="h-8 w-24 bg-severity-normal-bg rounded" />
        <div className="h-8 w-24 bg-severity-normal-bg rounded" />
        <div className="h-8 w-16 bg-severity-normal-bg rounded" />
      </div>
      <div className="h-3 w-full bg-severity-normal-bg rounded" />
    </div>
  );
}
