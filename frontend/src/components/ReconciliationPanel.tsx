import { ReconciliationCard, type ReconciliationItem } from "./ReconciliationCard";

interface ReconciliationPanelProps {
  reconciliations: ReconciliationItem[] | null | undefined;
}

function severityOf(delta: number): "high" | "medium" | "low" {
  const abs = Math.abs(delta);
  if (abs >= 5000) return "high";
  if (abs >= 500) return "medium";
  return "low";
}

const SEVERITY_ORDER = ["high", "medium", "low"] as const;

const SEVERITY_LABELS: Record<string, string> = {
  high: "High severity",
  medium: "Medium severity",
  low: "Low severity",
};

const SEVERITY_COLORS: Record<string, string> = {
  high: "text-severity-high-fg",
  medium: "text-severity-medium-fg",
  low: "text-text-secondary",
};

export function ReconciliationPanel({ reconciliations }: ReconciliationPanelProps) {
  if (!reconciliations || reconciliations.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-severity-normal-bg px-4 py-5 text-center">
        <p className="text-sm text-text-secondary">No discrepancies detected across files.</p>
      </div>
    );
  }

  const grouped: Record<string, ReconciliationItem[]> = { high: [], medium: [], low: [] };
  for (const item of reconciliations) {
    grouped[severityOf(item.delta)].push(item);
  }

  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
          Reconciliation findings
        </h2>
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs text-text-secondary tabular-nums">
          {reconciliations.length} item{reconciliations.length !== 1 ? "s" : ""}
        </span>
      </div>

      {SEVERITY_ORDER.map((level) => {
        const items = grouped[level];
        if (!items.length) return null;
        return (
          <div key={level} className="space-y-2">
            <p className={`text-xs font-semibold uppercase tracking-widest ${SEVERITY_COLORS[level]}`}>
              {SEVERITY_LABELS[level]} · {items.length}
            </p>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              {items.map((item, i) => (
                <ReconciliationCard key={`${item.account}-${i}`} {...item} severity={level} />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
