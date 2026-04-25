import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "../lib/utils";
import { formatCurrency } from "../lib/formatters";
import {
  ClassificationBadge,
  type Classification,
} from "./ClassificationBadge";
import { ProvenanceTooltip } from "./ProvenanceTooltip";

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

interface ReconciliationCardProps extends ReconciliationItem {}

export function ReconciliationCard({
  account,
  classification,
  delta,
  gl_amount,
  non_gl_total,
  narrative,
  suggested_action,
  sources,
}: ReconciliationCardProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(suggested_action).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  // Primary source file for provenance (first source, if any)
  const primarySource = sources?.[0] ?? null;

  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wide">
          {account}
        </h3>
        <ClassificationBadge
          classification={classification}
          className="shrink-0"
        />
      </div>

      {/* Numbers row */}
      <div className="flex flex-wrap gap-4 text-sm">
        <div>
          <span className="text-text-secondary text-xs block">GL</span>
          <ProvenanceTooltip sourceFile={null}>
            <span className="text-text-primary tabular-nums">
              {formatCurrency(gl_amount)}
            </span>
          </ProvenanceTooltip>
        </div>
        <div>
          <span className="text-text-secondary text-xs block">Source</span>
          <ProvenanceTooltip
            sourceFile={primarySource?.source_file ?? null}
            sourceColumn={primarySource?.source_column}
          >
            <span className="text-text-primary tabular-nums">
              {formatCurrency(non_gl_total)}
            </span>
          </ProvenanceTooltip>
        </div>
        <div>
          <span className="text-text-secondary text-xs block">Gap</span>
          <span
            className={cn(
              "tabular-nums font-medium",
              Math.abs(delta) > 0
                ? "text-severity-high-fg"
                : "text-favorable-fg"
            )}
          >
            {formatCurrency(Math.abs(delta))}
          </span>
        </div>
      </div>

      {/* Per-source breakdown chips (when multiple sources) */}
      {sources && sources.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {sources.map((s) => (
            <ProvenanceTooltip
              key={s.source_file}
              sourceFile={s.source_file}
              sourceColumn={s.source_column}
            >
              <span className="inline-flex items-center gap-1 rounded-md bg-severity-normal-bg px-2 py-0.5 text-xs text-text-secondary">
                <span className="font-mono truncate max-w-[120px]" title={s.source_file}>
                  {s.source_file.split("/").pop()}
                </span>
                <span className="text-text-secondary/70">
                  {formatCurrency(s.amount)}
                </span>
              </span>
            </ProvenanceTooltip>
          ))}
        </div>
      )}

      {/* Narrative */}
      <p className="text-sm text-text-secondary">{narrative}</p>

      {/* Suggested action */}
      <div className="flex items-center justify-between gap-3 rounded-md bg-severity-normal-bg px-3 py-2">
        <p className="text-xs text-text-secondary flex-1">{suggested_action}</p>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy suggested action"
          className={cn(
            "shrink-0 inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            copied
              ? "bg-favorable-bg text-favorable-fg"
              : "bg-surface text-text-secondary hover:text-text-primary border border-border"
          )}
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" aria-hidden />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" aria-hidden />
              Copy
            </>
          )}
        </button>
      </div>
    </div>
  );
}
