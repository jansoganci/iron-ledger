import { CheckCircle, AlertTriangle } from "lucide-react";
import type { TieOutSummary } from "../lib/tieOut";
import { cn } from "../lib/utils";

interface TieOutSummaryCardProps {
  summary: TieOutSummary;
}

export function TieOutSummaryCard({ summary }: TieOutSummaryCardProps) {
  const compared = summary.compared;
  const withGap = summary.with_gap;
  const notCompared = summary.not_compared;

  if (compared === 0 && notCompared === 0) {
    return (
      <section className="space-y-2" aria-labelledby="tie-out-heading">
        <div className="flex items-center gap-3">
          <h2
            id="tie-out-heading"
            className="text-xs font-semibold text-text-secondary uppercase tracking-widest"
          >
            Tie-out
          </h2>
          <div className="flex-1 h-px bg-border" />
        </div>
        <p className="text-sm text-text-secondary">
          No supporting files were compared. Upload payroll, vendor, or contract
          files next time to tie out the general ledger.
        </p>
      </section>
    );
  }

  const countLabel = [
    compared ? `${compared} compared` : null,
    withGap ? `${withGap} with a gap` : null,
    notCompared ? `${notCompared} not compared` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="space-y-3" aria-labelledby="tie-out-heading">
      <div className="flex items-center gap-3">
        <h2
          id="tie-out-heading"
          className="text-xs font-semibold text-text-secondary uppercase tracking-widest"
        >
          Tie-out
        </h2>
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs text-text-secondary tabular-nums">{countLabel}</span>
      </div>
      <ul className="divide-y divide-border rounded-lg border border-border">
        {summary.groups.map((group) => {
          const clean = group.status === "clean";
          return (
            <li
              key={group.key}
              className="flex items-center gap-3 px-4 py-3 bg-surface"
            >
              {clean ? (
                <CheckCircle
                  className="h-4 w-4 shrink-0 text-favorable-fg"
                  aria-hidden
                />
              ) : (
                <AlertTriangle
                  className="h-4 w-4 shrink-0 text-severity-medium-fg"
                  aria-hidden
                />
              )}
              <span className="flex-1 text-sm font-medium text-text-primary">
                {group.label}
              </span>
              <span
                className={cn(
                  "text-xs tabular-nums",
                  clean ? "text-favorable-fg" : "text-severity-medium-fg"
                )}
              >
                {clean ? "Tied out" : "Has a gap"}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
