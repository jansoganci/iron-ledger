import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { AlertTriangle, CheckCircle, Loader2, X } from "lucide-react";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";
import type { MappingDraft, MappingDraftItem } from "./LoadingProgress";

interface MappingReviewProps {
  runId: string;
  draft: MappingDraft;
  onConfirmed: () => void;
}

const LARGE_BATCH_CONFIRMATION_THRESHOLD = 10;

interface PendingBulkApply {
  file: string;
  account: string;
  usePayrollPreset: boolean;
}

function rowKeyFor(item: MappingDraftItem): string {
  return `${item.source_file}::${item.source_pattern}`;
}

export function MappingReview({ runId, draft, onConfirmed }: MappingReviewProps) {
  const sortedPool = [...draft.gl_account_pool].sort();

  // Selected values: seed confident rows with their suggestion, leave others empty
  const [selected, setSelected] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const item of draft.items) {
      if (item.confident && item.suggested_gl_account) {
        init[rowKeyFor(item)] = item.suggested_gl_account;
      }
    }
    return init;
  });
  const [bulkSelectedByFile, setBulkSelectedByFile] = useState<Record<string, string>>({});

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingBulkApply, setPendingBulkApply] = useState<PendingBulkApply | null>(null);

  // Group items by source_file
  const byFile = draft.items.reduce<Record<string, MappingDraftItem[]>>((acc, item) => {
    (acc[item.source_file] ??= []).push(item);
    return acc;
  }, {});

  const allResolved = draft.items.every((item) => !!selected[rowKeyFor(item)]);

  function applyAccountToItems(items: MappingDraftItem[], account: string): number {
    let updates = 0;
    setSelected((prev) => {
      const next = { ...prev };
      for (const item of items) {
        const key = rowKeyFor(item);
        if (next[key] !== account) {
          next[key] = account;
          updates += 1;
        }
      }
      return next;
    });
    return updates;
  }

  function executeBulkApply(
    file: string,
    items: MappingDraftItem[],
    account: string,
    usePayrollPreset = false
  ) {
    const appliedCount = applyAccountToItems(items, account);
    if (appliedCount > 0) {
      setError(null);
      setNotice(`Applied "${account}" to ${appliedCount} row${appliedCount === 1 ? "" : "s"} in ${file}.`);
    } else {
      setNotice(`All rows in ${file} already use "${account}".`);
    }
    if (usePayrollPreset) {
      setBulkSelectedByFile((prev) => ({ ...prev, [file]: account }));
    }
  }

  function requestBulkApply(
    file: string,
    items: MappingDraftItem[],
    account: string,
    usePayrollPreset = false
  ) {
    if (items.length > LARGE_BATCH_CONFIRMATION_THRESHOLD) {
      setPendingBulkApply({
        file,
        account,
        usePayrollPreset,
      });
      return;
    }
    executeBulkApply(file, items, account, usePayrollPreset);
  }

  function handleBulkApply(file: string, items: MappingDraftItem[]) {
    const account = bulkSelectedByFile[file];
    if (!account) return;
    requestBulkApply(file, items, account, false);
  }

  function handlePayrollQuickApply(file: string, items: MappingDraftItem[]) {
    const payrollAccount = "Salaries & Wages";
    if (!sortedPool.includes(payrollAccount)) return;
    requestBulkApply(file, items, payrollAccount, true);
  }

  function confirmPendingBulkApply() {
    if (!pendingBulkApply) return;
    const items = byFile[pendingBulkApply.file] ?? [];
    executeBulkApply(
      pendingBulkApply.file,
      items,
      pendingBulkApply.account,
      pendingBulkApply.usePayrollPreset
    );
    setPendingBulkApply(null);
  }

  async function handleSubmit() {
    if (!allResolved || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const decisions: Record<string, string> = {};
      const conflicts = new Set<string>();
      for (const item of draft.items) {
        const chosen = selected[rowKeyFor(item)];
        if (!chosen) continue;
        const existing = decisions[item.source_pattern];
        if (existing && existing !== chosen) {
          conflicts.add(item.source_pattern);
          continue;
        }
        decisions[item.source_pattern] = chosen;
      }

      if (conflicts.size > 0) {
        setError(
          `Conflicting selections found for: ${Array.from(conflicts).join(", ")}. Please choose one GL account per source value.`
        );
        setIsSubmitting(false);
        return;
      }

      await apiFetch(`/runs/${runId}/confirm-mappings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      });
      onConfirmed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm mappings.");
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog.Root
      open={!!pendingBulkApply}
      onOpenChange={(open) => {
        if (!open) setPendingBulkApply(null);
      }}
    >
      <div className="px-4 py-8 md:py-10">
        <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-text-primary">
            AI Account Mapping Review
          </h2>
          <p className="text-sm text-text-secondary">
            The system identified the following values in your files. Review and
            confirm the suggested GL account for each entry.
          </p>
        </div>

        {/* Per-file tables */}
        {Object.entries(byFile).map(([file, items]) => (
          <div
            key={file}
            className="rounded-lg border border-border bg-surface overflow-hidden"
          >
            <div className="px-4 py-2 bg-canvas border-b border-border space-y-2">
              <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide block">
                {file}
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className={cn(
                    "rounded border px-2 py-1 text-xs bg-surface text-text-primary",
                    "focus:outline-none focus:ring-2 focus:ring-accent border-border"
                  )}
                  value={bulkSelectedByFile[file] ?? ""}
                  onChange={(e) =>
                    setBulkSelectedByFile((prev) => ({
                      ...prev,
                      [file]: e.target.value,
                    }))
                  }
                >
                  <option value="">Choose account</option>
                  {sortedPool.map((acct) => (
                    <option key={`${file}-${acct}`} value={acct}>
                      {acct}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => handleBulkApply(file, items)}
                  disabled={!bulkSelectedByFile[file] || isSubmitting}
                  className={cn(
                    "rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-primary",
                    "hover:bg-severity-normal-bg transition-colors",
                    (!bulkSelectedByFile[file] || isSubmitting) &&
                      "opacity-50 cursor-not-allowed"
                  )}
                >
                  Apply to File
                </button>
                {items.some((item) => item.file_type === "payroll") &&
                  sortedPool.includes("Salaries & Wages") && (
                    <button
                      type="button"
                      onClick={() => handlePayrollQuickApply(file, items)}
                      disabled={isSubmitting}
                      className={cn(
                        "rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-primary",
                        "hover:bg-severity-normal-bg transition-colors",
                        isSubmitting && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      Set All to Salaries & Wages
                    </button>
                  )}
              </div>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-4 py-2 font-medium text-text-secondary text-xs">
                    Source Value
                  </th>
                  <th className="text-left px-4 py-2 font-medium text-text-secondary text-xs">
                    GL Account
                  </th>
                  <th className="text-left px-4 py-2 font-medium text-text-secondary text-xs w-24">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const key = rowKeyFor(item);
                  const value = selected[key] ?? "";
                  const unsure = !item.confident;

                  return (
                    <tr
                      key={key}
                      className={cn(
                        "border-b border-border last:border-0",
                        unsure && !value ? "bg-severity-medium-bg/30" : ""
                      )}
                    >
                      <td className="px-4 py-2 font-mono text-xs text-text-primary">
                        {item.source_pattern}
                      </td>
                      <td className="px-4 py-2">
                        <select
                          className={cn(
                            "w-full rounded border px-2 py-1 text-sm bg-surface text-text-primary",
                            "focus:outline-none focus:ring-2 focus:ring-accent",
                            unsure && !value
                              ? "border-severity-medium-fg"
                              : "border-border"
                          )}
                          value={value}
                          onChange={(e) =>
                            setSelected((prev) => ({
                              ...prev,
                              [key]: e.target.value,
                            }))
                          }
                        >
                          {!value && (
                            <option value="" disabled>
                              -- choose --
                            </option>
                          )}
                          {sortedPool.map((acct) => (
                            <option key={acct} value={acct}>
                              {acct}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        {item.confident ? (
                          <span className="inline-flex items-center gap-1 text-xs text-favorable-fg">
                            <CheckCircle className="h-3 w-3" aria-hidden />
                            Confident
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-severity-medium-fg">
                            <AlertTriangle className="h-3 w-3" aria-hidden />
                            Unsure
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}

        {/* Error */}
        {error && (
          <p className="text-sm text-severity-high-fg rounded-md bg-severity-high-bg px-3 py-2">
            {error}
          </p>
        )}
        {notice && (
          <p className="text-sm text-favorable-fg rounded-md bg-favorable-bg px-3 py-2">
            {notice}
          </p>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!allResolved || isSubmitting}
          className={cn(
            "w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white",
            "hover:bg-accent/90 transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
            (!allResolved || isSubmitting) && "opacity-50 cursor-not-allowed"
          )}
        >
          {isSubmitting ? (
            <span className="inline-flex items-center gap-2 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Applying mappings…
            </span>
          ) : !allResolved ? (
            "Select a GL account for all unsure rows to continue"
          ) : (
            "Confirm Mappings"
          )}
        </button>
        </div>
      </div>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30" />
        <Dialog.Content
          className={cn(
            "fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
            "w-full max-w-md rounded-lg bg-surface border border-border shadow-lg",
            "p-6 space-y-4 focus:outline-none"
          )}
        >
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-base font-semibold text-text-primary">
              Confirm Bulk Apply
            </Dialog.Title>
            <Dialog.Close className="text-text-secondary hover:text-text-primary">
              <X className="h-4 w-4" aria-hidden />
              <span className="sr-only">Close</span>
            </Dialog.Close>
          </div>

          {pendingBulkApply && (
            <p className="text-sm text-text-secondary">
              This will apply <span className="font-medium text-text-primary">{pendingBulkApply.account}</span>{" "}
              to all rows in <span className="font-medium text-text-primary">{pendingBulkApply.file}</span>.
              Continue?
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Dialog.Close
              className={cn(
                "rounded-md px-4 py-2 text-sm text-text-secondary",
                "hover:text-text-primary transition-colors"
              )}
            >
              Cancel
            </Dialog.Close>
            <button
              type="button"
              onClick={confirmPendingBulkApply}
              className={cn(
                "rounded-md bg-accent px-4 py-2 text-sm font-medium text-white",
                "hover:bg-accent/90 transition-colors",
                "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
              )}
            >
              Confirm
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
