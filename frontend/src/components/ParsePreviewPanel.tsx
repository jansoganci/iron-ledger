import { useState } from "react";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";
import { formatCurrency } from "../lib/formatters";
import type { ParsePreview, PreviewRow } from "./LoadingProgress";

function SourceBreakdownChips({ row }: { row: PreviewRow }) {
  if (!row.source_breakdown || row.source_breakdown.length === 0) {
    return <span className="text-xs text-text-secondary">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {row.source_breakdown.map((s) => (
        <span
          key={s.source_file}
          title={s.source_file}
          className="inline-flex items-center gap-1 rounded-md bg-severity-normal-bg px-1.5 py-0.5 text-[10px] text-text-secondary max-w-[140px]"
        >
          <span className="truncate font-data">{s.source_file.split("/").pop()}</span>
          <span className="shrink-0 text-text-secondary/70">{formatCurrency(s.amount)}</span>
        </span>
      ))}
    </div>
  );
}

const CATEGORIES = [
  "REVENUE",
  "COGS",
  "OPEX",
  "G&A",
  "R&D",
  "OTHER_INCOME",
  "OTHER",
  "SKIP",
];

const LOW_CONFIDENCE_THRESHOLD = 0.8;

interface ParsePreviewPanelProps {
  runId: string;
  preview: ParsePreview;
  onConfirmed: () => void;
}

export function ParsePreviewPanel({ runId, preview, onConfirmed }: ParsePreviewPanelProps) {
  const [categoryOverrides, setCategoryOverrides] = useState<Record<string, string>>({});
  const [amountOverrides, setAmountOverrides] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function categoryFor(row: PreviewRow): string {
    return categoryOverrides[row.account] ?? row.category;
  }

  function amountValueFor(row: PreviewRow): string {
    return amountOverrides[row.account] ?? String(row.amount);
  }

  function isAmountEdited(row: PreviewRow): boolean {
    const override = amountOverrides[row.account];
    if (override === undefined) return false;
    return parseFloat(override) !== row.amount;
  }

  function handleCategoryChange(account: string, category: string) {
    setCategoryOverrides((prev) => ({ ...prev, [account]: category }));
  }

  function handleAmountChange(account: string, value: string) {
    setAmountOverrides((prev) => ({ ...prev, [account]: value }));
  }

  async function handleConfirm() {
    // Validate edited amounts before touching the network
    for (const [account, value] of Object.entries(amountOverrides)) {
      const parsed = parseFloat(value);
      if (isNaN(parsed) || !isFinite(parsed)) {
        setError(`Invalid amount for "${account}". Please enter a valid number.`);
        return;
      }
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Merge category and amount overrides into a single list
      const allAccounts = new Set([
        ...Object.keys(categoryOverrides),
        ...Object.keys(amountOverrides),
      ]);

      const overrides = Array.from(allAccounts)
        .map((account) => {
          const obj: { account: string; category?: string; amount?: number } = { account };
          if (categoryOverrides[account] !== undefined) obj.category = categoryOverrides[account];
          if (amountOverrides[account] !== undefined) {
            const parsed = parseFloat(amountOverrides[account]);
            if (!isNaN(parsed)) obj.amount = parsed;
          }
          return obj;
        })
        .filter((o) => o.category !== undefined || o.amount !== undefined);

      await apiFetch(`/runs/${runId}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ overrides }),
      });
      onConfirmed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const skippedCount = preview.rows.filter((r) => categoryFor(r) === "SKIP").length;
  const writtenCount = preview.rows.length - skippedCount;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Review parsed data</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Check categories and amounts before they're written to the database. Amber rows have
          low confidence — review them carefully.
        </p>
      </div>

      <div className="max-h-96 overflow-y-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface border-b border-border">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-text-secondary">Account</th>
              <th className="px-3 py-2 text-left font-medium text-text-secondary">Category</th>
              <th className="px-3 py-2 text-right font-medium text-text-secondary">Amount</th>
              <th className="px-3 py-2 text-left font-medium text-text-secondary">Sources</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {preview.rows.map((row) => {
              const isLowConf = row.confidence < LOW_CONFIDENCE_THRESHOLD;
              const currentCategory = categoryFor(row);
              const isSkipped = currentCategory === "SKIP";
              const amountEdited = isAmountEdited(row);
              return (
                <tr
                  key={row.account}
                  className={cn(
                    isLowConf && "bg-amber-50 border-l-2 border-l-amber-400",
                    isSkipped && "opacity-40"
                  )}
                >
                  <td className="px-3 py-2 text-text-primary font-medium">
                    {row.account}
                    {isLowConf && (
                      <span className="ml-2 text-xs text-amber-600 font-normal">
                        low confidence
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={currentCategory}
                      onChange={(e) => handleCategoryChange(row.account, e.target.value)}
                      className={cn(
                        "rounded border border-border bg-surface px-2 py-1 text-xs",
                        "text-text-primary focus:outline-none focus:ring-1 focus:ring-accent",
                        "disabled:opacity-50"
                      )}
                      disabled={isSubmitting}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <input
                      type="number"
                      step="any"
                      value={amountValueFor(row)}
                      onChange={(e) => handleAmountChange(row.account, e.target.value)}
                      disabled={isSubmitting || isSkipped}
                      className={cn(
                        "w-32 rounded border bg-surface px-2 py-1 text-xs text-right tabular-nums",
                        "text-text-primary focus:outline-none focus:ring-1 focus:ring-accent",
                        "disabled:opacity-50",
                        amountEdited ? "border-accent ring-1 ring-accent" : "border-border"
                      )}
                    />
                    {amountEdited && (
                      <span className="block text-right text-[10px] text-accent mt-0.5">
                        edited
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <SourceBreakdownChips row={row} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {skippedCount > 0 && (
        <p className="text-xs text-text-secondary">
          {skippedCount} account{skippedCount > 1 ? "s" : ""} marked SKIP will not be written to
          the database.
        </p>
      )}

      {preview.drops && preview.drops.total_dropped > 0 && (
        <details className="text-xs text-text-secondary">
          <summary className="cursor-pointer select-none">
            {preview.drops.total_dropped} row
            {preview.drops.total_dropped > 1 ? "s" : ""} skipped during import
          </summary>
          <ul className="mt-2 space-y-1 pl-4">
            {preview.drops.entries.map((d) => (
              <li key={d.row_index}>
                Row {d.row_index + 1}: "{d.account_snippet || "(unnamed)"}" —{" "}
                {d.reason === "subtotal_safety_net" ? "subtotal" : "no amount"}
              </li>
            ))}
          </ul>
        </details>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        onClick={handleConfirm}
        disabled={isSubmitting || writtenCount === 0}
        className={cn(
          "w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white",
          "hover:bg-accent/90 transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
          (isSubmitting || writtenCount === 0) && "opacity-50 cursor-not-allowed"
        )}
      >
        {isSubmitting ? "Saving…" : "Confirm & Analyze →"}
      </button>
    </div>
  );
}
