import { ReconciliationCard, type ReconciliationItem } from "./ReconciliationCard";

interface ReconciliationPanelProps {
  reconciliations: ReconciliationItem[] | null | undefined;
}

export function ReconciliationPanel({ reconciliations }: ReconciliationPanelProps) {
  if (!reconciliations || reconciliations.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-severity-normal-bg px-4 py-5 text-center">
        <p className="text-sm text-text-secondary">
          No discrepancies detected across files.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-3">
      <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Reconciliation findings · {reconciliations.length} item
        {reconciliations.length !== 1 ? "s" : ""}
      </h2>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        {reconciliations.map((item, i) => (
          <ReconciliationCard key={`${item.account}-${i}`} {...item} />
        ))}
      </div>
    </section>
  );
}
