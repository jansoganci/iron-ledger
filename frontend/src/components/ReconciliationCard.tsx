import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "../lib/utils";
import { formatCurrency } from "../lib/formatters";
import type { Classification } from "./ClassificationBadge";

export interface ReconciliationSource {
  source_file: string;
  amount: number;
  source_column?: string | null;
}

export interface ReconciliationItem {
  account: string;
  classification: Classification | null;
  delta: number;
  gl_amount: number | null;
  non_gl_total: number;
  narrative: string | null;
  suggested_action: string | null;
  sources?: ReconciliationSource[];
}

interface ReconciliationCardProps extends ReconciliationItem {
  severity?: "high" | "medium" | "low";
}

// Plain-English status labels — no jargon
const STATUS_LABEL: Record<string, string> = {
  missing_je:                  "Not confirmed by your uploaded records",
  categorical_misclassification: "May be in the wrong category",
  timing_cutoff:               "Likely a timing difference",
  accrual_mismatch:            "Invoice may need to be spread monthly",
  stale_reference:             "Reference data may be outdated",
  structural_explained:        "Expected — no action needed",
};

const AMOUNT_COLOR: Record<string, string> = {
  high:   "text-severity-high-fg",
  medium: "text-severity-medium-fg",
  low:    "text-text-secondary",
};

export function ReconciliationCard({
  account,
  classification,
  delta,
  narrative,
  suggested_action,
  severity = "low",
}: ReconciliationCardProps) {
  const [copied, setCopied] = useState(false);

  const isExplained = classification === "structural_explained";
  const statusLabel = classification ? STATUS_LABEL[classification] : null;
  const amountColor = isExplained ? "text-favorable-fg" : (AMOUNT_COLOR[severity] ?? "text-text-secondary");

  function handleCopy() {
    navigator.clipboard.writeText(suggested_action ?? "").then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border p-4 space-y-3",
        isExplained ? "bg-severity-normal-bg opacity-70" : "bg-surface"
      )}
    >
      {/* Header: account name + amount */}
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-sm font-medium text-text-primary leading-snug">
          {account}
        </h3>
        <div className="text-right shrink-0">
          <p className={cn("text-base font-semibold tabular-nums", amountColor)}>
            {formatCurrency(Math.abs(delta))}
          </p>
          {statusLabel && (
            <p className="text-[11px] text-text-secondary mt-0.5 leading-tight max-w-[140px] text-right">
              {statusLabel}
            </p>
          )}
        </div>
      </div>

      {/* Narrative — only when non-empty */}
      {narrative && (
        <p className="text-sm text-text-secondary leading-relaxed">{narrative}</p>
      )}

      {/* Action — only when non-empty */}
      {suggested_action && !isExplained && (
        <div className="group flex items-start justify-between gap-2 pt-1">
          <p className="text-xs text-text-secondary flex-1">
            <span className="text-accent font-medium mr-1">→</span>
            {suggested_action}
          </p>
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy action"
            className={cn(
              "shrink-0 rounded p-1 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
              "opacity-0 group-hover:opacity-100",
              copied ? "text-favorable-fg" : "text-text-secondary hover:text-text-primary"
            )}
          >
            {copied
              ? <Check className="h-3.5 w-3.5" aria-hidden />
              : <Copy className="h-3.5 w-3.5" aria-hidden />}
          </button>
        </div>
      )}
    </div>
  );
}
