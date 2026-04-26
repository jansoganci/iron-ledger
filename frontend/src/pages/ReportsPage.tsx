import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ChevronsUpDown,
  FileText,
  Plus,
  Search,
  Upload as UploadIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ColumnDef,
  ColumnFiltersState,
  FilterFn,
  SortingState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  getReportLabel,
  getReportLink,
  ReportListItem,
} from "../components/HistoryList";
import { useCompany } from "../hooks/useCompany";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";

/**
 * Reports page — the filing cabinet.
 *
 * Monthly / Quarterly tabs (same pattern as Dashboard). Dense sortable table
 * (@tanstack/react-table); click column headers to sort, click a row to open.
 *
 * Mobile (<768px) redirected to /upload by AppShell's deep-link guard.
 */

interface ReportsListResponse {
  reports: ReportListItem[];
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function anomalyText(n: number): string {
  if (n === 0) return "No anomalies";
  return `${n} ${n === 1 ? "anomaly" : "anomalies"}`;
}

// Custom filter: match against the Period column label
const periodLabelFilter: FilterFn<ReportListItem> = (row, _columnId, value) => {
  try {
    const q = String(value).trim().toLowerCase();
    if (!q) return true;
    const label = getReportLabel(row.original);
    return label.toLowerCase().includes(q);
  } catch (error) {
    console.error("Error in periodLabelFilter:", error, row.original);
    return false;
  }
};

const columnHelper = createColumnHelper<ReportListItem>();

/** Returns the last N completed quarters as { label, path } */
function recentQuarters(count = 4): { label: string; path: string }[] {
  const now = new Date();
  const results = [];
  let year = now.getFullYear();
  // Start from the previous completed quarter (current quarter is in progress)
  let quarter = Math.ceil((now.getMonth() + 1) / 3) - 1;
  if (quarter === 0) {
    quarter = 4;
    year -= 1;
  }
  for (let i = 0; i < count; i++) {
    results.push({
      label: `Q${quarter} ${year}`,
      path: `/report/quarterly/${year}-Q${quarter}`,
    });
    quarter -= 1;
    if (quarter === 0) {
      quarter = 4;
      year -= 1;
    }
  }
  return results;
}

export default function ReportsPage() {
  const { data: company } = useCompany();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"monthly" | "quarterly">("monthly");

  const { data, isLoading } = useQuery<ReportsListResponse>({
    queryKey: ["reports-list", "full"],
    queryFn: () => apiFetch<ReportsListResponse>("/reports?limit=50"),
    staleTime: 30_000,
  });

  const [sorting, setSorting] = useState<SortingState>([
    { id: "period", desc: true },
  ]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [query, setQuery] = useState("");

  // Filter by active tab — useMemo so the array reference is stable
  const reports = useMemo(() => {
    const all = data?.reports ?? [];
    return all.filter((r) => r.report_type === activeTab);
  }, [data?.reports, activeTab]);

  function updateQuery(next: string) {
    setQuery(next);
    setColumnFilters(next.trim() ? [{ id: "period", value: next }] : []);
  }

  function switchTab(tab: "monthly" | "quarterly") {
    if (tab === activeTab) return;
    setActiveTab(tab);
    setQuery("");
    setColumnFilters([]);
    setSorting([{ id: "period", desc: true }]);
  }

  const columns = useMemo<ColumnDef<ReportListItem, any>[]>(
    () => [
      columnHelper.accessor((r) => (r.anomaly_count ?? 0) > 0, {
        id: "severity",
        header: () => <span className="sr-only">Severity</span>,
        enableSorting: true,
        sortDescFirst: true,
        cell: ({ getValue }) => {
          const hasAnomalies = getValue() as boolean;
          return (
            <span
              className={cn(
                "inline-block h-2 w-2 rounded-full",
                hasAnomalies
                  ? "bg-severity-medium-fg"
                  : "bg-severity-normal-fg opacity-50"
              )}
              aria-hidden
            />
          );
        },
      }),
      columnHelper.accessor("period", {
        header: "Period",
        enableSorting: true,
        filterFn: periodLabelFilter,
        cell: ({ row }) => (
          <span className="text-sm font-medium text-text-primary">
            {getReportLabel(row.original)}
          </span>
        ),
      }),
      columnHelper.accessor((r) => r.anomaly_count ?? 0, {
        id: "anomaly_count",
        header: "Anomalies",
        enableSorting: true,
        sortDescFirst: true,
        cell: ({ getValue }) => {
          const n = getValue() as number;
          const hasAnomalies = n > 0;
          return (
            <span
              className={cn(
                "text-xs tabular-nums",
                hasAnomalies
                  ? "text-severity-medium-fg font-medium"
                  : "text-text-secondary"
              )}
              data-numeric
            >
              {anomalyText(n)}
            </span>
          );
        },
      }),
      columnHelper.accessor("generated_at", {
        header: "Generated",
        enableSorting: true,
        sortDescFirst: true,
        cell: ({ getValue }) => (
          <span
            className="text-xs text-text-secondary tabular-nums"
            data-numeric
          >
            {formatDate(getValue() as string | null)}
          </span>
        ),
      }),
      columnHelper.display({
        id: "action",
        header: () => <span className="sr-only">Open</span>,
        cell: () => (
          <ChevronRight
            className="h-4 w-4 text-text-secondary"
            aria-hidden
          />
        ),
      }),
    ],
    []
  );

  const table = useReactTable({
    data: reports,
    columns,
    state: { sorting, columnFilters },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const totalCount = reports.length;
  const rows = table.getRowModel().rows;
  const shownCount = rows.length;

  const openRow = (report: ReportListItem) => navigate(getReportLink(report));

  return (
    <div className="px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-text-primary">Reports</h1>
            <p className="text-sm text-text-secondary mt-1">
              Every verified report
              {company?.name ? ` for ${company.name}` : ""}.
            </p>
          </div>
          <div
            className="text-sm text-text-secondary tabular-nums shrink-0"
            data-numeric
          >
            {isLoading
              ? "…"
              : totalCount === 1
                ? "1 total"
                : `${totalCount} total`}
          </div>
        </div>

        {/* Search */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">
              All reports
            </h2>
            
            {/* Tabs */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => switchTab("monthly")}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === "monthly"
                    ? "bg-accent text-white"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface"
                }`}
              >
                Monthly
              </button>
              <button
                type="button"
                onClick={() => switchTab("quarterly")}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === "quarterly"
                    ? "bg-accent text-white"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface"
                }`}
              >
                Quarterly
              </button>
            </div>
          </div>

          {/* Quarter picker — only shown when quarterly tab is active */}
          {activeTab === "quarterly" && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-text-secondary shrink-0">Generate:</span>
              {recentQuarters(4).map((q) => (
                <Link
                  key={q.path}
                  to={q.path}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border border-border bg-surface text-text-secondary hover:text-text-primary hover:border-accent transition-colors"
                >
                  <Plus className="h-3 w-3" aria-hidden />
                  {q.label}
                </Link>
              ))}
            </div>
          )}

          {/* Search */}
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary pointer-events-none"
              aria-hidden
            />
            <input
              type="search"
              value={query}
              onChange={(e) => updateQuery(e.target.value)}
              placeholder="Search by period…"
              aria-label="Search reports by period"
              className="w-full rounded-md border border-border bg-surface pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
            />
          </div>
        </div>

        {/* Table or empty state */}
        {isLoading ? (
          <ReportsTableSkeleton />
        ) : totalCount === 0 ? (
          activeTab === "quarterly" ? <NoQuarterlyReportsEmptyState /> : <NoReportsEmptyState />
        ) : shownCount === 0 ? (
          <NoMatchesEmptyState />
        ) : (
          <div className="rounded-lg border border-border bg-surface overflow-hidden">
            <table className="w-full text-left">
              <thead className="border-b border-border bg-canvas">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => {
                      const canSort = header.column.getCanSort();
                      const sortDir = header.column.getIsSorted();
                      const ariaSort: "ascending" | "descending" | "none" =
                        sortDir === "asc"
                          ? "ascending"
                          : sortDir === "desc"
                            ? "descending"
                            : "none";
                      const isNumericCol =
                        header.column.id === "anomaly_count" ||
                        header.column.id === "generated_at";
                      return (
                        <th
                          key={header.id}
                          scope="col"
                          aria-sort={canSort ? ariaSort : undefined}
                          className={cn(
                            "px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide",
                            header.column.id === "severity" && "w-8",
                            header.column.id === "action" && "w-8",
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
                {rows.map((row) => {
                  const label = getReportLabel(row.original);
                  return (
                    <tr
                      key={row.id}
                      tabIndex={0}
                      role="link"
                      aria-label={`Open report for ${label}`}
                      onClick={() => openRow(row.original)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          openRow(row.original);
                        }
                      }}
                      className="cursor-pointer hover:bg-canvas transition-colors focus:outline-none focus:bg-canvas focus:ring-2 focus:ring-accent focus:ring-inset"
                    >
                      {row.getVisibleCells().map((cell) => {
                        const isNumericCol =
                          cell.column.id === "anomaly_count" ||
                          cell.column.id === "generated_at";
                        return (
                          <td
                            key={cell.id}
                            className={cn(
                              "px-4 py-3 align-middle",
                              cell.column.id === "severity" && "w-8",
                              cell.column.id === "action" && "w-8 text-right",
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
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Result-count footer when filtered */}
        {!isLoading && query.trim() && totalCount > 0 && (
          <p
            className="text-xs text-text-secondary tabular-nums"
            data-numeric
            role="status"
            aria-live="polite"
          >
            {shownCount} of {totalCount} match "{query.trim()}"
          </p>
        )}
      </div>
    </div>
  );
}

// ----- Subcomponents ----- //

function SortIcon({ dir }: { dir: false | "asc" | "desc" }) {
  if (dir === "asc") return <ChevronUp className="h-3 w-3" aria-hidden />;
  if (dir === "desc") return <ChevronDown className="h-3 w-3" aria-hidden />;
  return <ChevronsUpDown className="h-3 w-3 opacity-50" aria-hidden />;
}

function ReportsTableSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="divide-y divide-border">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="px-4 py-3 flex items-center gap-4 animate-pulse"
          >
            <div className="h-2 w-2 rounded-full bg-severity-normal-bg" />
            <div className="h-4 w-32 bg-severity-normal-bg rounded" />
            <div className="flex-1" />
            <div className="h-3 w-24 bg-severity-normal-bg rounded" />
            <div className="h-3 w-24 bg-severity-normal-bg rounded" />
            <div className="h-4 w-4 bg-severity-normal-bg rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

function NoReportsEmptyState() {
  return (
    <div className="rounded-lg border border-border bg-surface p-8 text-center">
      <FileText
        className="h-8 w-8 text-text-secondary mx-auto mb-2 opacity-60"
        aria-hidden
      />
      <p className="text-sm font-medium text-text-primary">No reports yet</p>
      <p className="text-sm text-text-secondary mt-1 mb-4">
        Upload your first period to see analysis here.
      </p>
      <Link
        to="/upload"
        className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
      >
        <UploadIcon className="h-4 w-4" aria-hidden />
        Upload first period
      </Link>
    </div>
  );
}

function NoQuarterlyReportsEmptyState() {
  const quarters = recentQuarters(4);
  return (
    <div className="rounded-lg border border-border bg-surface p-8 text-center">
      <FileText
        className="h-8 w-8 text-text-secondary mx-auto mb-2 opacity-60"
        aria-hidden
      />
      <p className="text-sm font-medium text-text-primary">No quarterly reports yet</p>
      <p className="text-sm text-text-secondary mt-1 mb-5">
        Select a quarter below to generate your first quarterly summary.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {quarters.map((q) => (
          <Link
            key={q.path}
            to={q.path}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
          >
            <Plus className="h-4 w-4" aria-hidden />
            {q.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

function NoMatchesEmptyState() {
  return (
    <div className="rounded-lg border border-border bg-surface p-8 text-center">
      <p className="text-sm text-text-primary font-medium">
        No reports match your search
      </p>
      <p className="text-sm text-text-secondary mt-1">
        Try a different period, or clear the search to see everything.
      </p>
    </div>
  );
}
