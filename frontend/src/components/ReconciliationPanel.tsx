import {
  ReconciliationCard,
  isCoverageItem,
  type ReconciliationItem,
} from "./ReconciliationCard";
import {
  TIE_OUT_GROUP_LABELS,
  TIE_OUT_GROUP_ORDER,
  tieOutGroupFromSources,
  type TieOutGroupKey,
} from "../lib/tieOut";

interface ReconciliationPanelProps {
  reconciliations: ReconciliationItem[] | null | undefined;
}

function severityOf(delta: number): "high" | "medium" | "low" {
  const abs = Math.abs(delta);
  if (abs >= 5000) return "high";
  if (abs >= 500) return "medium";
  return "low";
}

function groupOf(item: ReconciliationItem): TieOutGroupKey {
  if (item.tie_out_group) return item.tie_out_group;
  return (
    tieOutGroupFromSources(
      item.sources,
      item.card_kind,
      item.hints?.is_gl_only
    ) ?? "other"
  );
}

export function ReconciliationPanel({ reconciliations }: ReconciliationPanelProps) {
  const items = reconciliations ?? [];
  const exceptions = items.filter((item) => !isCoverageItem(item));
  const coverage = items.filter((item) => isCoverageItem(item));

  if (exceptions.length === 0 && coverage.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-severity-normal-bg px-4 py-5 text-center">
        <p className="text-sm text-text-secondary">No discrepancies detected across files.</p>
      </div>
    );
  }

  const grouped = new Map<TieOutGroupKey, ReconciliationItem[]>();
  for (const item of exceptions) {
    const key = groupOf(item);
    const list = grouped.get(key) ?? [];
    list.push(item);
    grouped.set(key, list);
  }

  const countLabel = [
    exceptions.length ? `${exceptions.length} to review` : null,
    coverage.length ? `${coverage.length} not compared` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
          Exceptions
        </h2>
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs text-text-secondary tabular-nums">
          {countLabel}
        </span>
      </div>

      {TIE_OUT_GROUP_ORDER.map((key) => {
        const levelItems = grouped.get(key);
        if (!levelItems?.length) return null;
        const sorted = [...levelItems].sort(
          (a, b) => Math.abs(b.delta) - Math.abs(a.delta)
        );
        return (
          <div key={key} className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">
              {TIE_OUT_GROUP_LABELS[key]} · {sorted.length}
            </p>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              {sorted.map((item, i) => (
                <ReconciliationCard
                  key={`${item.account}-${i}`}
                  {...item}
                  severity={severityOf(item.delta)}
                />
              ))}
            </div>
          </div>
        );
      })}

      {coverage.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">
            Not compared · {coverage.length}
          </p>
          <p className="text-xs text-text-secondary">
            These general-ledger accounts were not in any uploaded supporting file.
            That is not a missing journal entry.
          </p>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {coverage.map((item, i) => (
              <ReconciliationCard key={`cov-${item.account}-${i}`} {...item} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
