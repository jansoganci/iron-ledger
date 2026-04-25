import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Calendar,
  FileText,
  Upload as UploadIcon,
} from "lucide-react";
import { Link } from "react-router-dom";
import { HistoryList, ReportListItem } from "../components/HistoryList";
import { MetricCard } from "../components/MetricCard";
import { useCompany } from "../hooks/useCompany";
import { apiFetch } from "../lib/api";
import { formatPeriod } from "../lib/formatters";

/**
 * Dashboard per docs/design.md §4 — basit overview of what data the user has,
 * their latest report, and total anomalies detected. Hidden on <768px
 * (AppShell redirects to /upload with an info toast).
 */

interface HasHistoryResponse {
  has_history: boolean;
  periods_loaded: number;
}

interface ReportsListResponse {
  reports: ReportListItem[];
}

export default function DashboardPage() {
  const { data: company } = useCompany();

  const { data: history } = useQuery<HasHistoryResponse>({
    queryKey: ["has-history"],
    queryFn: () => apiFetch<HasHistoryResponse>("/companies/me/has-history"),
    staleTime: 30_000,
  });

  const { data: reportsData, isLoading: reportsLoading } =
    useQuery<ReportsListResponse>({
      queryKey: ["reports-list"],
      queryFn: () => apiFetch<ReportsListResponse>("/reports?limit=12"),
      staleTime: 30_000,
    });

  const reports = reportsData?.reports ?? [];
  const latest = reports[0];
  const totalAnomalies = reports.reduce(
    (sum, r) => sum + (r.anomaly_count ?? 0),
    0
  );
  const periodsLoaded = history?.periods_loaded ?? 0;

  return (
    <div className="px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Dashboard</h1>
          <p className="text-sm text-text-secondary mt-1">
            {company?.name ? `${company.name} · ` : ""}Overview of your loaded
            data and recent reports.
          </p>
        </div>

        {/* Metric strip — 3-col desktop, 2-col tablet (wraps), 1-col stacked below md */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <MetricCard
            label="Periods loaded"
            value={periodsLoaded}
            subtext={
              periodsLoaded === 1 ? "month of data" : "months of data"
            }
            icon={<Calendar className="h-4 w-4" />}
          />
          <MetricCard
            label="Latest report"
            value={latest ? formatPeriod(latest.period) : "—"}
            subtext={
              latest
                ? latest.anomaly_count === 0
                  ? "No anomalies this period"
                  : `${latest.anomaly_count} ${
                      latest.anomaly_count === 1 ? "item" : "items"
                    } flagged`
                : "Upload a file to generate your first report"
            }
            icon={<FileText className="h-4 w-4" />}
          />
          <MetricCard
            label="Total anomalies"
            value={totalAnomalies}
            subtext={
              periodsLoaded > 0
                ? `Across ${periodsLoaded} ${
                    periodsLoaded === 1 ? "period" : "periods"
                  }`
                : "—"
            }
            icon={<AlertTriangle className="h-4 w-4" />}
          />
        </div>

        {/* Recent reports */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-text-primary">
            Recent reports
          </h2>
          <HistoryList reports={reports} loading={reportsLoading} />
        </div>

        {/* Action */}
        <div className="flex justify-end pt-2">
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 min-h-[44px] lg:min-h-[40px]"
          >
            <UploadIcon className="h-4 w-4" aria-hidden />
            Upload new period
          </Link>
        </div>
      </div>
    </div>
  );
}
