const _currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  currencySign: "accounting",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(n: number | null | undefined): string {
  if (n == null || isNaN(n as number)) return "$0.00";
  return _currencyFmt.format(n);
}

export function formatPeriod(iso: string): string {
  try {
    // Parse as local date to avoid UTC offset shifting the month
    const [year, month] = iso.split("-").map(Number);
    return new Date(year, month - 1, 1).toLocaleDateString("en-US", {
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function formatVariance(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

/** Generate ISO period options (first-of-month) going back N months from today (includes current month). */
export function recentPeriods(count = 24): { label: string; value: string }[] {
  const options: { label: string; value: string }[] = [];
  const today = new Date();
  for (let i = 0; i < count; i++) {
    const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
    options.push({ label: formatPeriod(iso), value: iso });
  }
  return options;
}

/** Returns the ISO string for N months before today (first of that month). */
export function monthsAgo(n: number): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}
