import { formatCurrency } from "../lib/formatters";

export interface YtdValues {
  revenue: number;
  cogs: number;
  gross_profit: number;
  operating_expenses: number;
  general_administrative: number;
  net_profit: number;
}

export interface YtdSummary {
  through_month: number | null;
  last_loaded_month: number | null;
  months: { month: number; values: YtdValues | null }[];
  totals: YtdValues | null;
  has_unclassified_accounts: boolean;
}

const LINES: { key: keyof YtdValues; label: string }[] = [
  { key: "revenue", label: "Revenue" },
  { key: "cogs", label: "Cost of goods sold" },
  { key: "gross_profit", label: "Gross profit" },
  { key: "operating_expenses", label: "Operating expenses" },
  { key: "general_administrative", label: "General & administrative" },
  { key: "net_profit", label: "Net profit" },
];

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function YtdSummaryTable({
  year,
  summary,
  isLoading,
  isError,
}: {
  year: number;
  summary: YtdSummary | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return <p className="text-sm text-text-secondary">Loading year summary…</p>;
  }
  if (isError) {
    return <p className="text-sm text-text-secondary">Could not load the year summary.</p>;
  }
  const title = summary?.through_month
    ? `${year}, January through ${MONTH_NAMES[summary.through_month - 1]}`
    : `${year}`;
  if (!summary?.through_month || !summary.totals) {
    return (
      <section className="space-y-3" aria-labelledby="ytd-title">
        <h2 id="ytd-title" className="text-sm font-semibold text-text-primary">
          {title}
        </h2>
        <div className="rounded-lg border border-border bg-surface p-8 text-center">
          <p className="text-sm text-text-secondary">
            No general ledger data has been uploaded for this period yet.
          </p>
        </div>
      </section>
    );
  }
  const totals = summary.totals;

  return (
    <section className="space-y-3" aria-labelledby="ytd-title">
      <h2 id="ytd-title" className="text-sm font-semibold text-text-primary">
        {title}
      </h2>
      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-border bg-canvas">
              <tr>
                <th scope="col" className="sticky left-0 bg-canvas px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide whitespace-nowrap">
                  Account group
                </th>
                {summary.months.map(({ month }) => (
                  <th key={month} scope="col" className="px-4 py-2.5 text-right text-xs font-medium text-text-secondary uppercase tracking-wide whitespace-nowrap">
                    {MONTH_NAMES[month - 1]}
                  </th>
                ))}
                <th scope="col" className="px-4 py-2.5 text-right text-xs font-medium text-text-secondary uppercase tracking-wide whitespace-nowrap">
                  Year to date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {LINES.map(({ key, label }) => (
                <tr key={key} className="hover:bg-canvas transition-colors">
                  <th scope="row" className="sticky left-0 bg-surface px-4 py-3 text-sm font-medium text-text-primary whitespace-nowrap">
                    {label}
                  </th>
                  {summary.months.map(({ month, values }) => (
                    <td key={month} className="px-4 py-3 text-right text-sm font-data text-text-primary whitespace-nowrap" data-numeric>
                      {values ? formatCurrency(values[key]) : "—"}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right text-sm font-data font-medium text-text-primary whitespace-nowrap" data-numeric>
                    {formatCurrency(totals[key])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {summary.has_unclassified_accounts && (
        <p className="text-xs text-text-secondary">
          Accounts classified as OTHER are excluded from this summary.
        </p>
      )}
    </section>
  );
}
