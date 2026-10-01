import { useState } from "react";
import { Lock, LockOpen } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiErrorDetail,
  closePeriod,
  getPeriodClose,
  reopenPeriod,
  type PeriodCloseState,
} from "../lib/api";
import { formatPeriod } from "../lib/formatters";
import { CLIENT_MESSAGES } from "../lib/messages";

interface PeriodClosePanelProps {
  period: string;
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * A person's sign-off on a finished monthly report. Separate from "Numbers
 * verified", which is never a close. Closing and reopening each need their own
 * confirmation here and are enforced again on the server.
 */
export function PeriodClosePanel({ period }: PeriodClosePanelProps) {
  const queryClient = useQueryClient();
  const key = ["period-close", period];
  const [confirming, setConfirming] = useState<"close" | "reopen" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery<PeriodCloseState>({
    queryKey: key,
    queryFn: () => getPeriodClose(period),
  });

  const mutation = useMutation({
    mutationFn: (action: "close" | "reopen") =>
      action === "close" ? closePeriod(period) : reopenPeriod(period),
    onSuccess: (state) => {
      queryClient.setQueryData(key, state);
      setConfirming(null);
      setError(null);
    },
    onError: (err) => {
      setError(apiErrorDetail(err, CLIENT_MESSAGES.PERIOD_CLOSE_FAILED));
    },
  });

  if (!data) return null;

  const label = formatPeriod(period);
  const busy = mutation.isPending;
  const closed = data.closed && data.close;
  const who = closed
    ? data.close!.closed_by_you
      ? "you"
      : data.close!.closed_by_email ?? "another user"
    : null;

  return (
    <section
      aria-labelledby="period-close-heading"
      className="rounded-xl border border-border bg-surface px-8 py-6 space-y-3"
    >
      <div className="flex items-center gap-3">
        <h2
          id="period-close-heading"
          className="text-xs font-semibold text-text-secondary uppercase tracking-widest"
        >
          Period close
        </h2>
        <div className="flex-1 h-px bg-border" />
      </div>

      {closed ? (
        <div className="flex items-start gap-3">
          <Lock className="h-4 w-4 mt-0.5 text-text-secondary shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="text-sm font-medium text-text-primary">
              {label} is closed
            </p>
            <p className="text-sm text-text-secondary">
              Closed on {formatWhen(data.close!.closed_at)} by {who}. Uploads and
              replacements are blocked until you reopen it.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3">
          <LockOpen className="h-4 w-4 mt-0.5 text-text-secondary shrink-0" aria-hidden />
          <p className="text-sm text-text-secondary">
            {label} is open. Closing is your sign-off that you reviewed this
            report; it does not happen automatically.
          </p>
        </div>
      )}

      {confirming ? (
        <div
          role="alertdialog"
          aria-labelledby="period-close-confirm"
          className="rounded-lg border border-border bg-canvas p-4 space-y-3"
        >
          <p id="period-close-confirm" className="text-sm text-text-primary">
            {confirming === "close"
              ? `Close ${label}? Your name and the time are saved, and uploads and replacements are blocked until you reopen it.`
              : `Reopen ${label}? The close stays on record, a reopen entry is added, and you can upload or replace data again.`}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => mutation.mutate(confirming)}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
            >
              {confirming === "close" ? "Yes, close this period" : "Yes, reopen this period"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setConfirming(null);
                setError(null);
              }}
              className="rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(closed ? "reopen" : "close")}
          className="rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas focus:outline-none focus:ring-2 focus:ring-accent"
        >
          {closed ? "Reopen this period" : "Close this period"}
        </button>
      )}

      {error && <p className="text-sm text-severity-high-fg">{error}</p>}

      {data.log.length > 0 && (
        <ul className="text-xs text-text-secondary space-y-0.5">
          {data.log.map((entry, i) => (
            <li key={i}>
              {entry.event === "closed" ? "Closed" : "Reopened"} ·{" "}
              {formatWhen(entry.created_at)}
              {entry.actor_email ? ` · ${entry.actor_email}` : ""}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
