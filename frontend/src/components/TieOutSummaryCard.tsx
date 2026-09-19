import { CheckCircle, AlertTriangle, CircleHelp, FileQuestion } from "lucide-react";
import type { ControlResult, ControlStatus, TieOutSummary } from "../lib/tieOut";
import { CONTROL_STATUS_LABEL } from "../lib/tieOut";
import { formatCurrency } from "../lib/formatters";
import { cn } from "../lib/utils";

interface TieOutSummaryCardProps {
  summary: TieOutSummary;
}

function StatusIcon({ status }: { status: ControlStatus }) {
  if (status === "tied_out") {
    return (
      <CheckCircle className="h-4 w-4 shrink-0 text-favorable-fg" aria-hidden />
    );
  }
  if (status === "has_exceptions") {
    return (
      <AlertTriangle
        className="h-4 w-4 shrink-0 text-severity-medium-fg"
        aria-hidden
      />
    );
  }
  if (status === "mapping_required") {
    return (
      <CircleHelp className="h-4 w-4 shrink-0 text-severity-medium-fg" aria-hidden />
    );
  }
  return (
    <FileQuestion className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden />
  );
}

function ControlRow({ control }: { control: ControlResult }) {
  const statusLabel = CONTROL_STATUS_LABEL[control.status];
  const tone =
    control.status === "tied_out"
      ? "text-favorable-fg"
      : control.status === "has_exceptions" || control.status === "mapping_required"
        ? "text-severity-medium-fg"
        : "text-text-secondary";

  return (
    <li className="px-4 py-3 bg-surface space-y-2">
      <div className="flex items-start gap-3">
        <StatusIcon status={control.status} />
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-text-primary">
              {control.label}
            </span>
            <span className={cn("text-xs tabular-nums", tone)}>{statusLabel}</span>
          </div>
          <p className="text-xs text-text-secondary">{control.next_action}</p>
          {control.source_file && (
            <p className="text-xs text-text-secondary">
              Source: {control.source_file}
              {control.amount_scope ? ` · ${control.amount_scope}` : ""}
            </p>
          )}
          {control.gl_targets.length > 0 && (
            <p className="text-xs text-text-secondary">
              GL: {control.gl_targets.join(", ")}
            </p>
          )}
          {control.incomplete_reason && (
            <p className="text-xs text-text-secondary">{control.incomplete_reason}</p>
          )}
        </div>
      </div>
      {control.comparisons.length > 0 && (
        <ul className="ml-7 space-y-1">
          {control.comparisons.map((cmp) => (
            <li key={cmp.gl_account} className="text-xs text-text-secondary">
              <span className="font-medium text-text-primary">{cmp.gl_account}</span>
              {" · "}
              source {cmp.supporting_amount == null ? "—" : formatCurrency(cmp.supporting_amount)}
              {" · "}
              GL {cmp.gl_amount == null ? "—" : formatCurrency(cmp.gl_amount)}
              {cmp.difference != null && (
                <>
                  {" · "}
                  difference {formatCurrency(cmp.difference)}
                </>
              )}
              {cmp.classification && (
                <>
                  {" · "}
                  {cmp.classification.replace(/_/g, " ")}
                </>
              )}
              {!cmp.complete && cmp.incomplete_reason
                ? ` · ${cmp.incomplete_reason}`
                : null}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function TieOutSummaryCard({ summary }: TieOutSummaryCardProps) {
  const controls = summary.controls ?? [];
  const compared = summary.compared ?? 0;
  const withExceptions = summary.with_exceptions ?? summary.with_gap ?? 0;
  const notEvaluated = summary.not_evaluated ?? 0;
  const coverageCount = summary.coverage_account_count ?? summary.not_compared ?? 0;

  if (controls.length === 0 && compared === 0 && coverageCount === 0) {
    return (
      <section className="space-y-2" aria-labelledby="tie-out-heading">
        <div className="flex items-center gap-3">
          <h2
            id="tie-out-heading"
            className="text-xs font-semibold text-text-secondary uppercase tracking-widest"
          >
            Close controls
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
    withExceptions ? `${withExceptions} with exceptions` : null,
    notEvaluated ? `${notEvaluated} not evaluated` : null,
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
          Close controls
        </h2>
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs text-text-secondary tabular-nums">{countLabel}</span>
      </div>
      <ul className="divide-y divide-border rounded-lg border border-border">
        {controls.map((control) => (
          <ControlRow key={control.key} control={control} />
        ))}
      </ul>
      {summary.scope_note && (
        <p className="text-xs text-text-secondary">{summary.scope_note}</p>
      )}
    </section>
  );
}
