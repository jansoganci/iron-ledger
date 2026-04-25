import { useState } from "react";
import { apiFetch } from "../lib/api";
import { useToast } from "./ToastProvider";
import { cn } from "../lib/utils";

const CATEGORIES = [
  "REVENUE",
  "COGS",
  "OPEX",
  "G&A",
  "R&D",
  "OTHER_INCOME",
  "OTHER",
  "SKIP",
] as const;

export interface LowConfidenceColumn {
  column: string;
  agent_guess: string;
  confidence: number;
}

interface RowState {
  column: string;
  category: string; // current selection
  skipped: boolean;
}

interface MappingConfirmPanelProps {
  runId: string;
  columns: LowConfidenceColumn[];
  onConfirmed: () => void;
}

export function MappingConfirmPanel({ runId, columns, onConfirmed }: MappingConfirmPanelProps) {
  // Max 3 rows, lowest confidence first
  const displayed = [...columns]
    .sort((a, b) => a.confidence - b.confidence)
    .slice(0, 3);

  const [rows, setRows] = useState<RowState[]>(
    displayed.map((c) => ({
      column: c.column,
      category: c.agent_guess || "OTHER",
      skipped: false,
    }))
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const toast = useToast();

  const allResolved = rows.every((r) => r.category !== "" || r.skipped);
  const canConfirm = allResolved && !isSubmitting;

  function setCategory(idx: number, category: string) {
    setRows((prev) =>
      prev.map((r, i) =>
        i === idx ? { ...r, category, skipped: category === "SKIP" } : r
      )
    );
  }

  function skipRow(idx: number) {
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, skipped: true, category: "SKIP" } : r))
    );
  }

  async function handleConfirm() {
    if (!canConfirm) return;
    setIsSubmitting(true);

    const mappings = rows.map((r) => ({
      column: r.column,
      category: r.category,
    }));

    try {
      await apiFetch(`/runs/${runId}/mapping/confirm`, {
        method: "POST",
        json: { mappings },
      });
      toast.success("Column mappings saved. Future uploads will auto-map these.");
      setSubmitted(true);
      onConfirmed();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Could not save mappings. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) return null;

  return (
    <div className="rounded-lg border border-border bg-surface p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-text-primary">
          We auto-mapped these columns. Please review.
        </h2>
        <p className="text-xs text-text-secondary mt-0.5">
          Most of your file mapped cleanly. We're not sure about{" "}
          {displayed.length === 1 ? "this one" : `these ${displayed.length}`} — please confirm.
        </p>
      </div>

      <div className="space-y-3">
        {displayed.map((col, idx) => {
          const row = rows[idx];
          const isSkipped = row.skipped;
          return (
            <div
              key={col.column}
              className={cn(
                "rounded-md border border-border p-3 space-y-2",
                isSkipped && "opacity-50"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-text-primary">{col.column}</p>
                  <p className="text-xs text-text-secondary">
                    Agent's guess:{" "}
                    <span className="font-medium">{col.agent_guess}</span>
                    {"  "}
                    <span className="text-text-secondary">
                      ({Math.round(col.confidence * 100)}% confidence)
                    </span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <select
                  value={row.category}
                  onChange={(e) => setCategory(idx, e.target.value)}
                  disabled={isSkipped || isSubmitting}
                  className={cn(
                    "flex-1 rounded-md border border-border bg-surface px-2 py-1.5",
                    "text-sm text-text-primary",
                    "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1",
                    (isSkipped || isSubmitting) && "opacity-60 cursor-not-allowed"
                  )}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c === "SKIP" ? "— Skip this column —" : c}
                    </option>
                  ))}
                </select>

                {!isSkipped && (
                  <button
                    onClick={() => skipRow(idx)}
                    disabled={isSubmitting}
                    className="text-xs text-text-secondary hover:text-text-primary underline shrink-0"
                  >
                    Skip this column
                  </button>
                )}
                {isSkipped && (
                  <span className="text-xs text-text-secondary shrink-0">Skipped</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleConfirm}
          disabled={!canConfirm}
          className={cn(
            "rounded-md bg-accent px-4 py-2 text-sm font-medium text-white",
            "hover:bg-accent/90 transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
            !canConfirm && "opacity-50 cursor-not-allowed"
          )}
        >
          {isSubmitting ? "Saving…" : "Confirm Mappings"}
        </button>
      </div>
    </div>
  );
}
