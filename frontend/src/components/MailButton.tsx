import * as Dialog from "@radix-ui/react-dialog";
import { Mail, X } from "lucide-react";
import { useState } from "react";
import { formatPeriod } from "../lib/formatters";
import { cn } from "../lib/utils";

interface MailButtonProps {
  reportId: string;
  summary: string;
  companyName: string;
  period: string;
  anomalyCount: number;
}

export function MailButton({ summary, companyName, period, anomalyCount }: MailButtonProps) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");

  function buildMailto(to: string): string {
    const periodLabel = formatPeriod(period);
    const subject = `IronLedger Close Package - ${companyName} - ${periodLabel}`;
    const body = [
      `Period: ${periodLabel}`,
      `Anomalies detected: ${anomalyCount}`,
      "",
      summary,
      "",
      "Please attach the Excel close package from IronLedger before sending.",
    ].join("\n");
    return `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }

  function handleOpen() {
    if (!email) return;
    window.location.href = buildMailto(email);
    setOpen(false);
    setEmail("");
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          className={cn(
            "inline-flex items-center gap-2 rounded-md border border-border",
            "px-4 py-2 text-sm font-medium text-text-primary bg-surface",
            "hover:bg-canvas transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
          )}
        >
          <Mail className="h-4 w-4" aria-hidden />
          Send Email
        </button>
      </Dialog.Trigger>

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
              Send Report by Email
            </Dialog.Title>
            <Dialog.Close className="text-text-secondary hover:text-text-primary">
              <X className="h-4 w-4" aria-hidden />
              <span className="sr-only">Close</span>
            </Dialog.Close>
          </div>

          <div className="space-y-1">
            <label
              htmlFor="mail-to"
              className="block text-sm font-medium text-text-primary"
            >
              Recipient email
            </label>
            <input
              id="mail-to"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="cfo@company.com"
              autoComplete="email"
              className={cn(
                "w-full rounded-md border border-border bg-surface px-3 py-2",
                "text-sm text-text-primary placeholder:text-text-secondary",
                "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1"
              )}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleOpen();
              }}
            />
          </div>

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
              onClick={handleOpen}
              disabled={!email}
              className={cn(
                "rounded-md bg-accent px-4 py-2 text-sm font-medium text-white",
                "hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all",
                "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
                !email && "opacity-50 cursor-not-allowed scale-100"
              )}
            >
              Open in Email
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
