import { formatCurrency, formatPeriod, formatVariance } from "./formatters";

interface DataEntry {
  period: string;
  account: string;
  category: string;
  amount: number;
  variance_pct: number | null;
  source_file: string | null;
  source_column: string | null;
}

export function exportToCSV(data: DataEntry[], filename: string): void {
  if (!data || data.length === 0) {
    return;
  }

  const headers = [
    "Period",
    "Account",
    "Category",
    "Amount",
    "Variance %",
    "Source File",
    "Source Column",
  ];

  const csvRows: string[] = [];
  csvRows.push(headers.join(","));

  for (const entry of data) {
    const row = [
      formatPeriod(entry.period),
      escapeCSV(entry.account),
      entry.category,
      formatCurrency(entry.amount),
      entry.variance_pct !== null ? formatVariance(entry.variance_pct) : "—",
      entry.source_file ? escapeCSV(entry.source_file) : "—",
      entry.source_column ? escapeCSV(entry.source_column) : "—",
    ];
    csvRows.push(row.join(","));
  }

  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);

  link.setAttribute("href", url);
  link.setAttribute("download", filename);
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function escapeCSV(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
