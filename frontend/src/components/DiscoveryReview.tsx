import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";
import type { DiscoveryPlanPayload } from "./LoadingProgress";

interface DiscoveryReviewProps {
  runId: string;
  plan: DiscoveryPlanPayload;
  onApproved: () => void;
  onRejected: () => void;
}

export function DiscoveryReview({
  runId,
  plan,
  onApproved,
  onRejected,
}: DiscoveryReviewProps) {
  const [busyAction, setBusyAction] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const previewRows = useMemo(() => {
    return (plan._preview ?? []).slice(0, 8).map((row) =>
      row.map((cell) => (cell == null || String(cell).trim() === "" ? "—" : String(cell)))
    );
  }, [plan._preview]);

  async function handleApprove() {
    if (busyAction) return;
    setBusyAction("approve");
    setError(null);
    try {
      await apiFetch(`/runs/${runId}/confirm-discovery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      onApproved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not confirm file structure.");
      setBusyAction(null);
    }
  }

  async function handleReject() {
    if (busyAction) return;
    setBusyAction("reject");
    setError(null);
    try {
      await apiFetch(`/runs/${runId}/reject-discovery`, {
        method: "POST",
      });
      onRejected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reject file structure.");
      setBusyAction(null);
    }
  }

  return (
    <div className="px-4 py-8 md:py-10">
      <div className="max-w-2xl mx-auto space-y-4 rounded-lg border border-border bg-surface p-4 md:p-6 shadow-sm">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-text-primary">Confirm file structure</h2>
          <p className="text-sm text-text-secondary">
            We need your confirmation before continuing. Review the detected structure preview.
          </p>
          <p className="text-xs text-text-secondary">
            Confidence: {(plan.discovery_confidence * 100).toFixed(0)}%
          </p>
        </div>

        {previewRows.length > 0 && (
          <div className="overflow-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <tbody className="divide-y divide-border">
                {previewRows.map((row, idx) => (
                  <tr key={idx}>
                    {row.map((cell, cellIdx) => (
                      <td key={`${idx}-${cellIdx}`} className="px-2 py-1 text-text-secondary">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {error && (
          <p className="rounded-md bg-severity-high-bg px-3 py-2 text-sm text-severity-high-fg">
            {error}
          </p>
        )}

        <div className="grid gap-2 sm:grid-cols-2">
          <button
            onClick={handleApprove}
            disabled={busyAction !== null}
            className={cn(
              "rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white",
              "hover:bg-accent/90 transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
              busyAction !== null && "opacity-50 cursor-not-allowed"
            )}
          >
            {busyAction === "approve" ? (
              <span className="inline-flex items-center gap-2 justify-center">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Continuing...
              </span>
            ) : (
              "Looks correct, continue"
            )}
          </button>
          <button
            onClick={handleReject}
            disabled={busyAction !== null}
            className={cn(
              "rounded-md border border-severity-high-fg px-4 py-2.5 text-sm font-medium text-severity-high-fg",
              "hover:bg-severity-high-bg transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-severity-high-fg focus:ring-offset-2",
              busyAction !== null && "opacity-50 cursor-not-allowed"
            )}
          >
            {busyAction === "reject" ? (
              <span className="inline-flex items-center gap-2 justify-center">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Rejecting...
              </span>
            ) : (
              "This looks wrong"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
