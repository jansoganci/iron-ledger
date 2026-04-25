import { useQuery } from "@tanstack/react-query";
import { Download, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { useMemo, useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ColumnDef,
  SortingState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useCompany } from "../hooks/useCompany";
import { apiFetch } from "../lib/api";
import { formatCurrency, formatPeriod, formatVariance } from "../lib/formatters";
import { cn } from "../lib/utils";
import { exportToCSV } from "../lib/exportCSV";

interface DataEntry {
  period: string;
  account: string;
  category: string;
  amount: number;
  variance_pct: number | null;
  source_file: string | null;
  source_column: string | null;
}

interface DataResponse {
  year: number;
  total_amount: number;
  account_count: number;
  entries: DataEntry[];
}

const CATEGORIES = ["REVENUE", "COGS", "OPEX", "G&A", "R&D", "OTHER_INCOME", "OTHER"];
const MONTHS = [
  { value: "all", label: "All" },
  { value: "01", label: "Jan" },
  { value: "02", label: "Feb" },
  { value: "03", label: "Mar" },
  { value: "04", label: "Apr" },
  { value: "05", label: "May" },
  { value: "06", label: "Jun" },
  { value: "07", label: "Jul" },
  { value: "08", label: "Aug" },
  { value: "09", label: "Sep" },
  { value: "10", label: "Oct" },
  { value: "11", label: "Nov" },
  { value: "12", label: "Dec" },
];

const YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026];

const columnHelper = createColumnHelper<DataEntry>();

export default function DataPage() {
  const { data: company } = useCompany();
  const [searchParams] = useSearchParams();
  
  const initialYear = searchParams.get("year");
  const initialMonth = searchParams.get("month");
  
  const [selectedYear, setSelectedYear] = useState<number | null>(
    initialYear ? parseInt(initialYear) : null
  );
  const [selectedMonth, setSelectedMonth] = useState(initialMonth || "all");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "period", desc: true },
  ]);

  useEffect(() => {
    const yearParam = searchParams.get("year");
    const monthParam = searchParams.get("month");
    
    if (yearParam) {
      const year = parseInt(yearParam);
      if (!isNaN(year)) {
        setSelectedYear(year);
      }
    }
    
    if (monthParam) {
      setSelectedMonth(monthParam);
    }
  }, [searchParams]);

  const { data, isLoading } = useQuery<DataResponse>({
    queryKey: ["data", selectedYear],
    queryFn: () => apiFetch<DataResponse>(`/data?year=${selectedYear}`),
    enabled: selectedYear !== null,
    staleTime: 30_000,
  });

  const filteredData = useMemo(() => {
    if (!data?.entries) return [];
    
    let filtered = data.entries;
    
    if (selectedMonth !== "all") {
      filtered = filtered.filter((entry) => {
        const month = entry.period.split("-")[1];
        return month === selectedMonth;
      });
    }
    
    if (selectedCategory) {
      filtered = filtered.filter((entry) => entry.category === selectedCategory);
    }
    
    return filtered;
  }, [data?.entries, selectedMonth, selectedCategory]);

  const metrics = useMemo(() => {
    if (!filteredData.length) {
      return { totalAmount: 0, accountCount: 0 };
    }
    
    const totalAmount = filteredData.reduce((sum, entry) => sum + entry.amount, 0);
    const accountCount = filteredData.length;
    
    return { totalAmount, accountCount };
  }, [filteredData]);

  const columns = useMemo<ColumnDef<DataEntry, any>[]>(
    () => [
      columnHelper.accessor("period", {
        header: "Period",
        enableSorting: true,
        cell: ({ getValue }) => (
          <span className="text-sm font-medium text-text-primary">
            {formatPeriod(getValue() as string)}
          </span>
        ),
      }),
      columnHelper.accessor("account", {
        header: "Account Name",
        enableSorting: true,
        cell: ({ getValue }) => (
          <span className="text-sm text-text-primary">{getValue() as string}</span>
        ),
      }),
      columnHelper.accessor("category", {
        header: "Category",
        enableSorting: true,
        cell: ({ getValue }) => (
          <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">
            {getValue() as string}
          </span>
        ),
      }),
      columnHelper.accessor("amount", {
        header: "Amount",
        enableSorting: true,
        sortDescFirst: true,
        cell: ({ getValue }) => (
          <span className="text-sm tabular-nums text-text-primary" data-numeric>
            {formatCurrency(getValue() as number)}
          </span>
        ),
      }),
      columnHelper.accessor("variance_pct", {
        header: "Variance %",
        enableSorting: true,
        sortDescFirst: true,
        cell: ({ getValue }) => {
          const value = getValue() as number | null;
          return (
            <span className="text-sm tabular-nums text-text-secondary" data-numeric>
              {value !== null ? formatVariance(value) : "—"}
            </span>
          );
        },
      }),
      columnHelper.accessor("source_file", {
        header: "Source File",
        enableSorting: true,
        cell: ({ getValue }) => (
          <span className="text-xs text-text-secondary">
            {(getValue() as string | null) || "—"}
          </span>
        ),
      }),
      columnHelper.accessor("source_column", {
        header: "Source Column",
        enableSorting: true,
        cell: ({ getValue }) => (
          <span className="text-xs text-text-secondary">
            {(getValue() as string | null) || "—"}
          </span>
        ),
      }),
    ],
    []
  );

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  function handleExportCSV() {
    if (!filteredData.length) return;
    
    const filename = `ironledger-data-${selectedYear}${
      selectedMonth !== "all" ? `-${selectedMonth}` : ""
    }${selectedCategory ? `-${selectedCategory}` : ""}.csv`;
    
    exportToCSV(filteredData, filename);
  }

  return (
    <div className="px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Data</h1>
          <p className="text-sm text-text-secondary mt-1">
            {company?.name ? `${company.name} · ` : ""}View all uploaded financial data
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 flex gap-3">
            <select
              value={selectedYear ?? ""}
              onChange={(e) => {
                const year = e.target.value ? parseInt(e.target.value) : null;
                setSelectedYear(year);
                setSelectedMonth("all");
                setSelectedCategory(null);
              }}
              className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
            >
              <option value="">Please select a year</option>
              {YEARS.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>

            <select
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              disabled={!selectedYear}
              className={cn(
                "rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent",
                !selectedYear && "opacity-50 cursor-not-allowed"
              )}
            >
              {MONTHS.map((month) => (
                <option key={month.value} value={month.value}>
                  {month.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedYear && (
          <>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  selectedCategory === null
                    ? "bg-accent text-white"
                    : "bg-surface border border-border text-text-secondary hover:text-text-primary hover:bg-canvas"
                )}
              >
                All
              </button>
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                    selectedCategory === cat
                      ? "bg-accent text-white"
                      : "bg-surface border border-border text-text-secondary hover:text-text-primary hover:bg-canvas"
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-lg border border-border bg-surface">
              <div className="flex flex-col sm:flex-row gap-4">
                <div>
                  <span className="text-xs text-text-secondary">Total Amount</span>
                  <div className="text-lg font-semibold text-text-primary tabular-nums" data-numeric>
                    {formatCurrency(metrics.totalAmount)}
                  </div>
                </div>
                <div className="border-l border-border pl-4">
                  <span className="text-xs text-text-secondary">Accounts</span>
                  <div className="text-lg font-semibold text-text-primary tabular-nums" data-numeric>
                    {metrics.accountCount}
                  </div>
                </div>
              </div>
              <button
                onClick={handleExportCSV}
                disabled={!filteredData.length}
                className={cn(
                  "inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas transition-colors focus:outline-none focus:ring-2 focus:ring-accent",
                  !filteredData.length && "opacity-50 cursor-not-allowed"
                )}
              >
                <Download className="h-4 w-4" aria-hidden />
                Export CSV
              </button>
            </div>
          </>
        )}

        {!selectedYear ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center">
            <p className="text-sm font-medium text-text-primary">
              Please select a year to view data
            </p>
            <p className="text-sm text-text-secondary mt-1">
              Choose a year from the dropdown above to display your uploaded financial entries.
            </p>
          </div>
        ) : isLoading ? (
          <DataTableSkeleton />
        ) : filteredData.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center">
            <p className="text-sm font-medium text-text-primary">
              No data found
            </p>
            <p className="text-sm text-text-secondary mt-1">
              {selectedMonth !== "all" || selectedCategory
                ? "Try adjusting your filters to see more results."
                : "No financial data has been uploaded for this year yet."}
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-surface overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="border-b border-border bg-canvas sticky top-0 z-10">
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => {
                        const canSort = header.column.getCanSort();
                        const sortDir = header.column.getIsSorted();
                        const ariaSort: "ascending" | "descending" | "none" =
                          sortDir === "asc"
                            ? "ascending"
                            : sortDir === "desc"
                              ? "descending"
                              : "none";
                        const isNumericCol =
                          header.column.id === "amount" ||
                          header.column.id === "variance_pct";
                        return (
                          <th
                            key={header.id}
                            scope="col"
                            aria-sort={canSort ? ariaSort : undefined}
                            className={cn(
                              "px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide",
                              isNumericCol && "text-right"
                            )}
                          >
                            {canSort ? (
                              <button
                                type="button"
                                onClick={header.column.getToggleSortingHandler()}
                                className={cn(
                                  "inline-flex items-center gap-1 rounded-sm hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                                  isNumericCol && "flex-row-reverse"
                                )}
                              >
                                <span>
                                  {flexRender(
                                    header.column.columnDef.header,
                                    header.getContext()
                                  )}
                                </span>
                                <SortIcon dir={sortDir} />
                              </button>
                            ) : (
                              flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )
                            )}
                          </th>
                        );
                      })}
                    </tr>
                  ))}
                </thead>
                <tbody className="divide-y divide-border">
                  {table.getRowModel().rows.map((row, idx) => (
                    <tr
                      key={row.id}
                      className={cn(
                        "hover:bg-canvas transition-colors",
                        idx % 2 === 0 ? "bg-surface" : "bg-canvas/30"
                      )}
                    >
                      {row.getVisibleCells().map((cell) => {
                        const isNumericCol =
                          cell.column.id === "amount" ||
                          cell.column.id === "variance_pct";
                        return (
                          <td
                            key={cell.id}
                            className={cn(
                              "px-4 py-3 align-middle",
                              isNumericCol && "text-right"
                            )}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SortIcon({ dir }: { dir: false | "asc" | "desc" }) {
  if (dir === "asc") return <ChevronUp className="h-3 w-3" aria-hidden />;
  if (dir === "desc") return <ChevronDown className="h-3 w-3" aria-hidden />;
  return <ChevronsUpDown className="h-3 w-3 opacity-50" aria-hidden />;
}

function DataTableSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="divide-y divide-border">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="px-4 py-3 flex items-center gap-4 animate-pulse"
          >
            <div className="h-4 w-24 bg-severity-normal-bg rounded" />
            <div className="h-4 w-32 bg-severity-normal-bg rounded" />
            <div className="h-4 w-20 bg-severity-normal-bg rounded" />
            <div className="flex-1" />
            <div className="h-4 w-24 bg-severity-normal-bg rounded" />
            <div className="h-4 w-16 bg-severity-normal-bg rounded" />
            <div className="h-4 w-32 bg-severity-normal-bg rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
