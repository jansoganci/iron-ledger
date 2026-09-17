import { useEffect, useState } from "react";
import { CLIENT_MESSAGES } from "../lib/messages";

interface BankAttestationProps {
  storageKey: string;
}

function readSessionFlag(key: string): boolean {
  try {
    return sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeSessionFlag(key: string, value: boolean): void {
  try {
    if (value) sessionStorage.setItem(key, "1");
    else sessionStorage.removeItem(key);
  } catch {
    /* private mode — stay in memory only */
  }
}

export function BankAttestation({ storageKey }: BankAttestationProps) {
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    setChecked(readSessionFlag(storageKey));
  }, [storageKey]);

  function onChange(next: boolean) {
    setChecked(next);
    writeSessionFlag(storageKey, next);
  }

  const checkboxId = `bank-attestation-${storageKey.replace(/[^a-zA-Z0-9_-]/g, "-")}`;

  return (
    <section className="space-y-3" aria-labelledby="bank-attestation-heading">
      <div className="flex items-center gap-3">
        <h2
          id="bank-attestation-heading"
          className="text-xs font-semibold text-text-secondary uppercase tracking-widest"
        >
          Bank rec
        </h2>
        <div className="flex-1 h-px bg-border" />
      </div>
      <p className="text-sm text-text-secondary">
        {CLIENT_MESSAGES.BANK_OUTSIDE_ATTESTATION}
      </p>
      <label
        htmlFor={checkboxId}
        className="flex items-start gap-3 text-sm text-text-primary cursor-pointer"
      >
        <input
          id={checkboxId}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0 rounded border-border text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
        />
        <span>I confirmed bank and card rec outside this tool</span>
      </label>
    </section>
  );
}
