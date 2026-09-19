import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { AlertTriangle, Bookmark, Loader2, Sparkles, X } from "lucide-react";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";
import { formatCurrency } from "../lib/formatters";
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
}

type ItemOrigin = "new" | "remembered" | "conflict";

function originOf(item: MappingDraftItem): ItemOrigin {
  return item.origin ?? "new";
}

function rowKeyFor(item: MappingDraftItem): string {
  return `${item.source_file}::${item.source_pattern}`;
}

function groupByFile(items: MappingDraftItem[]): Record<string, MappingDraftItem[]> {
  return items.reduce<Record<string, MappingDraftItem[]>>((acc, item) => {
    (acc[item.source_file] ??= []).push(item);
    return acc;
  }, {});
}

export function MappingReview({ runId, draft, onConfirmed }: MappingReviewProps) {
  const sortedPool = [...draft.gl_account_pool].sort();
  const fileTotalItems = draft.items.filter(
    (item) => item.mapping_mode === "file_total"
  );
  const reviewItems = draft.items.filter(
    (item) => item.mapping_mode !== "file_total"
  );

  const [selected, setSelected] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const item of [...reviewItems, ...fileTotalItems]) {
      const origin = originOf(item);
      if (origin === "conflict") continue;
      if (item.suggested_gl_account && (origin === "remembered" || item.confident)) {
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

  const conflicts = reviewItems.filter((item) => originOf(item) === "conflict");
  const newcomers = reviewItems.filter((item) => originOf(item) === "new");
  const remembered = reviewItems.filter((item) => originOf(item) === "remembered");
  const allResolved =
    reviewItems.every((item) => !!selected[rowKeyFor(item)]) &&
    fileTotalItems.every((item) => !!selected[rowKeyFor(item)]);

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

  function executeBulkApply(file: string, items: MappingDraftItem[], account: string) {
    const appliedCount = applyAccountToItems(items, account);
    if (appliedCount > 0) {
      setError(null);
      setNotice(
        `Applied "${account}" to ${appliedCount} row${appliedCount === 1 ? "" : "s"} in ${file}.`
      );
    } else {
      setNotice(`All rows in ${file} already use "${account}".`);
    }
  }

  function requestBulkApply(file: string, items: MappingDraftItem[], account: string) {
    if (items.length > LARGE_BATCH_CONFIRMATION_THRESHOLD) {
      setPendingBulkApply({ file, account });
      return;
    }
    executeBulkApply(file, items, account);
  }

  function handleBulkApply(file: string, items: MappingDraftItem[]) {
    const account = bulkSelectedByFile[file];
    if (!account) return;
    requestBulkApply(file, items, account);
  }

  function confirmPendingBulkApply() {
    if (!pendingBulkApply) return;
    const items = reviewItems.filter((item) => item.source_file === pendingBulkApply.file);
    executeBulkApply(pendingBulkApply.file, items, pendingBulkApply.account);
    setPendingBulkApply(null);
  }

  async function handleSubmit() {
    if (!allResolved || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const decisions: Record<string, string> = {};
      const fileTotalDecisions: Record<string, string> = {};
      const clashes = new Set<string>();
      for (const item of reviewItems) {
        const chosen = selected[rowKeyFor(item)];
        if (!chosen) continue;
        const existing = decisions[item.source_pattern];
        if (existing && existing !== chosen) {
          clashes.add(item.source_pattern);
          continue;
        }
        decisions[item.source_pattern] = chosen;
      }
      for (const item of fileTotalItems) {
        const chosen = selected[rowKeyFor(item)];
        if (!chosen) continue;
        fileTotalDecisions[item.source_file] = chosen;
      }

      if (clashes.size > 0) {
        setError(
          `Conflicting selections found for: ${Array.from(clashes).join(", ")}. Please choose one GL account per source value.`
        );
        setIsSubmitting(false);
        return;
      }

      await apiFetch(`/runs/${runId}/confirm-mappings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decisions,
          file_total_decisions: fileTotalDecisions,
        }),
      });
      onConfirmed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm mappings.");
      setIsSubmitting(false);
    }
  }

  const sections: { key: ItemOrigin; title: string; hint: string; items: MappingDraftItem[] }[] = [
    {
      key: "conflict",
      title: "Needs your choice",
      hint: "Last month’s saved account and this month’s suggestion disagree. Pick one.",
      items: conflicts,
    },
    {
      key: "new",
      title: "New names",
      hint: "We have not saved these vendor or expense names yet.",
      items: newcomers,
    },
    {
      key: "remembered",
      title: "Already saved",
      hint: "These will be reused next month. Change a row if this month is different.",
      items: remembered,
    },
  ];

  return (
    <Dialog.Root
      open={!!pendingBulkApply}
      onOpenChange={(open) => {
        if (!open) setPendingBulkApply(null);
      }}
    >
      <div className="px-4 py-8 md:py-10">
        <div className="max-w-2xl mx-auto space-y-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-text-primary">
            Confirm source-to-GL mapping
          </h2>
          <p className="text-sm text-text-secondary">
            Confirm where each supporting file or line should land before we
            compare it to the general ledger. File totals and payroll roles are
            not saved as vendor names.
          </p>
          <p className="text-xs text-text-secondary">
            {conflicts.length} need a choice · {newcomers.length} new · {remembered.length} already saved
          </p>
        </div>

        {fileTotalItems.length > 0 && (
          <section className="space-y-3" aria-labelledby="map-file-total">
            <div>
              <h3
                id="map-file-total"
                className="text-sm font-semibold text-text-primary"
              >
                File totals
              </h3>
              <p className="text-xs text-text-secondary">
                This file’s amount for the period will be compared to one GL
                account. Confirm or correct the target before we run the control.
              </p>
            </div>
            <div className="space-y-3">
              {fileTotalItems.map((item) => {
                const key = rowKeyFor(item);
                return (
                  <div
                    key={key}
                    className="rounded-md border border-border p-3 space-y-2"
                  >
                    <p className="text-sm font-medium text-text-primary">
                      {item.source_file}
                    </p>
                    <p className="text-xs text-text-secondary">
                      Period {item.period ?? "this close month"}
                      {item.amount_scope ? ` · ${item.amount_scope}` : ""}
                      {item.source_amount != null
                        ? ` · ${formatCurrency(item.source_amount)}`
                        : ""}
                    </p>
                    <label className="block text-xs text-text-secondary">
                      GL account
                      <select
                        value={selected[key] ?? ""}
                        onChange={(e) =>
                          setSelected((prev) => ({
                            ...prev,
                            [key]: e.target.value,
                          }))
                        }
                        disabled={isSubmitting}
                        className={cn(
                          "mt-1 w-full rounded-md border border-border bg-surface px-2 py-1.5",
                          "text-sm text-text-primary",
                          "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1"
                        )}
                      >
                        <option value="">Select a GL account</option>
                        {sortedPool.map((account) => (
                          <option key={account} value={account}>
                            {account}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {sections.map((section) => {
          if (section.items.length === 0) return null;
          const byFile = groupByFile(section.items);
          return (
            <section key={section.key} className="space-y-3" aria-labelledby={`map-${section.key}`}>
              <div>
                <h3
                  id={`map-${section.key}`}
                  className="text-sm font-semibold text-text-primary"
                >
                  {section.title}
                </h3>
                <p className="text-xs text-text-secondary">{section.hint}</p>
              </div>
              {Object.entries(byFile).map(([file, items]) => (
                <FileMappingTable
                  key={`${section.key}-${file}`}
                  file={file}
                  items={items}
                  sortedPool={sortedPool}
                  selected={selected}
                  bulkValue={bulkSelectedByFile[file] ?? ""}
                  isSubmitting={isSubmitting}
                  onBulkValue={(value) =>
                    setBulkSelectedByFile((prev) => ({ ...prev, [file]: value }))
                  }
                  onBulkApply={() => handleBulkApply(file, items)}
                  onSelect={(item, value) =>
                    setSelected((prev) => ({ ...prev, [rowKeyFor(item)]: value }))
                  }
                />
              ))}
            </section>
          );
        })}

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
            "Choose an account for every highlighted name to continue"
          ) : (
            "Confirm names"
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

function FileMappingTable({
  file,
  items,
  sortedPool,
  selected,
  bulkValue,
  isSubmitting,
  onBulkValue,
  onBulkApply,
  onSelect,
}: {
  file: string;
  items: MappingDraftItem[];
  sortedPool: string[];
  selected: Record<string, string>;
  bulkValue: string;
  isSubmitting: boolean;
  onBulkValue: (value: string) => void;
  onBulkApply: () => void;
  onSelect: (item: MappingDraftItem, value: string) => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="px-4 py-2 bg-canvas border-b border-border space-y-2">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide block">
          {file}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label={`Choose account for all rows in ${file}`}
            className={cn(
              "rounded border px-2 py-1 text-xs bg-surface text-text-primary",
              "focus:outline-none focus:ring-2 focus:ring-accent border-border"
            )}
            value={bulkValue}
            onChange={(e) => onBulkValue(e.target.value)}
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
            onClick={onBulkApply}
            disabled={!bulkValue || isSubmitting}
            className={cn(
              "rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-primary",
              "hover:bg-severity-normal-bg transition-colors",
              (!bulkValue || isSubmitting) && "opacity-50 cursor-not-allowed"
            )}
          >
            Apply to File
          </button>
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
            <th className="text-left px-4 py-2 font-medium text-text-secondary text-xs w-28">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const key = rowKeyFor(item);
            const value = selected[key] ?? "";
            const origin = originOf(item);
            const needsChoice = !value;

            return (
              <tr
                key={key}
                className={cn(
                  "border-b border-border last:border-0",
                  origin === "conflict" && needsChoice && "bg-severity-medium-bg/30"
                )}
              >
                <td className="px-4 py-2 font-data text-xs text-text-primary">
                  <div>{item.source_pattern}</div>
                  {origin === "conflict" && (
                    <p className="text-[11px] text-text-secondary mt-1">
                      Saved: {item.remembered_gl_account ?? "—"} · Suggestion:{" "}
                      {item.haiku_gl_account ?? "—"}
                    </p>
                  )}
                </td>
                <td className="px-4 py-2">
                  <select
                    aria-label={`GL account for ${item.source_pattern}`}
                    className={cn(
                      "w-full rounded border px-2 py-1 text-sm bg-surface text-text-primary",
                      "focus:outline-none focus:ring-2 focus:ring-accent",
                      needsChoice ? "border-severity-medium-fg" : "border-border"
                    )}
                    value={value}
                    onChange={(e) => onSelect(item, e.target.value)}
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
                  <OriginBadge origin={origin} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function OriginBadge({ origin }: { origin: ItemOrigin }) {
  if (origin === "remembered") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-favorable-fg">
        <Bookmark className="h-3 w-3" aria-hidden />
        Saved
      </span>
    );
  }
  if (origin === "conflict") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-severity-medium-fg">
        <AlertTriangle className="h-3 w-3" aria-hidden />
        Choose
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-text-secondary">
      <Sparkles className="h-3 w-3" aria-hidden />
      New
    </span>
  );
}
