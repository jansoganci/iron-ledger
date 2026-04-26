import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  DollarSign,
  TrendingUp,
  Upload as UploadIcon,
} from "lucide-react";
import { Link } from "react-router-dom";
import { HistoryList, ReportListItem } from "../components/HistoryList";
import { MetricCard } from "../components/MetricCard";
import { useCompany } from "../hooks/useCompany";
import { apiFetch } from "../lib/api";
import { formatCurrency, formatPeriod } from "../lib/formatters";
import { cn } from "../lib/utils";

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

interface ReportFinancials {
  revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  opex: number;
  net_income: number;
  net_margin_pct: number;
}

interface FullReportResponse {
  period: string;
  generated_at: string | null;
  narrative: string;
  anomaly_count: number;
  error_count: number;
  anomalies: any[];
  financials: ReportFinancials;
}

export default function DashboardPage() {
  const { data: company } = useCompany();
  const [activeTab, setActiveTab] = useState<"monthly" | "quarterly">("monthly");

  const { data: history } = useQuery<HasHistoryResponse>({
    queryKey: ["has-history"],
    queryFn: () => apiFetch<HasHistoryResponse>("/companies/me/has-history"),
    staleTime: 30_000,
  });

  const { data: reportsData, isLoading: reportsLoading } =
    useQuery<ReportsListResponse>({
      queryKey: ["reports-list"],
      queryFn: () => apiFetch<ReportsListResponse>("/reports?limit=50"),
      staleTime: 30_000,
    });

  const allReports = reportsData?.reports ?? [];
  const monthlyReports = allReports.filter((r) => r.report_type === "monthly");
  const quarterlyReports = allReports.filter((r) => r.report_type === "quarterly");
  
  const reports = activeTab === "monthly" ? monthlyReports : quarterlyReports;
  const latest = monthlyReports[0];
  const previous = monthlyReports[1];
  const totalAnomalies = monthlyReports.reduce(
    (sum, r) => sum + (r.anomaly_count ?? 0),
    0
  );
  const periodsLoaded = history?.periods_loaded ?? 0;

  // Fetch latest report's full details (including financials)
  const { data: latestReportData } = useQuery<FullReportResponse>({
    queryKey: ["latest-report-financials", latest?.period],
    queryFn: () => apiFetch<FullReportResponse>(`/report/${company!.id}/${latest!.period}`),
    enabled: !!company?.id && !!latest,
    staleTime: 60_000,
  });

  // Fetch previous report's financials for MoM comparison
  const { data: previousReportData } = useQuery<FullReportResponse>({
    queryKey: ["previous-report-financials", previous?.period],
    queryFn: () => apiFetch<FullReportResponse>(`/report/${company!.id}/${previous!.period}`),
    enabled: !!company?.id && !!previous,
    staleTime: 60_000,
  });

  const latestFinancials = latestReportData?.financials;
  const previousFinancials = previousReportData?.financials;

  // Calculate MoM changes
  const calculateMoM = (current?: number, previous?: number): number | null => {
    if (!current || !previous || previous === 0) return null;
    return ((current - previous) / Math.abs(previous)) * 100;
  };

  const revenueMoM = calculateMoM(latestFinancials?.revenue, previousFinancials?.revenue);
  const netIncomeMoM = calculateMoM(latestFinancials?.net_income, previousFinancials?.net_income);
  const grossMarginChange = latestFinancials && previousFinancials
    ? latestFinancials.gross_margin_pct - previousFinancials.gross_margin_pct
    : null;

  // Count critical anomalies (high + medium severity)
  const criticalAnomalyCount = latestReportData?.anomalies?.filter(
    (a) => a.severity === "high" || a.severity === "medium"
  ).length ?? 0;

  return (
    <div className="px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-text-primary">Dashboard</h1>
            <p className="text-sm text-text-secondary mt-1">
              {company?.name ? `${company.name} · ` : ""}Overview of your loaded
              data and recent reports.
            </p>
          </div>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 min-h-[44px] lg:min-h-[40px]"
          >
            <UploadIcon className="h-4 w-4" aria-hidden />
            Upload new period
          </Link>
        </div>

        {/* Financial KPIs — 2 rows × 3 cols */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {/* Revenue */}
          <MetricCard
            label="Revenue"
            value={latestFinancials ? formatCurrency(latestFinancials.revenue) : "—"}
            subtext={
              revenueMoM !== null ? (
                <span className="flex items-center gap-1">
                  {revenueMoM >= 0 ? (
                    <ArrowUp className="h-3 w-3 text-favorable-fg" />
                  ) : (
                    <ArrowDown className="h-3 w-3 text-severity-high-fg" />
                  )}
                  <span className={cn("font-data", revenueMoM >= 0 ? "text-favorable-fg" : "text-severity-high-fg")} data-numeric>
                    {Math.abs(revenueMoM).toFixed(1)}% MoM
                  </span>
                </span>
              ) : (
                latest ? formatPeriod(latest.period) : "No data"
              )
            }
            icon={<DollarSign className="h-4 w-4" />}
          />

          {/* Gross Margin % */}
          <MetricCard
            label="Gross Margin"
            value={latestFinancials ? `${latestFinancials.gross_margin_pct.toFixed(1)}%` : "—"}
            subtext={
              grossMarginChange !== null ? (
                <span className="flex items-center gap-1">
                  {grossMarginChange >= 0 ? (
                    <ArrowUp className="h-3 w-3 text-favorable-fg" />
                  ) : (
                    <ArrowDown className="h-3 w-3 text-severity-high-fg" />
                  )}
                  <span className={cn("font-data", grossMarginChange >= 0 ? "text-favorable-fg" : "text-severity-high-fg")} data-numeric>
                    {Math.abs(grossMarginChange).toFixed(1)}pp
                  </span>
                </span>
              ) : (
                "vs previous month"
              )
            }
            icon={<TrendingUp className="h-4 w-4" />}
          />

          {/* Net Income */}
          <MetricCard
            label="Net Income"
            value={latestFinancials ? formatCurrency(latestFinancials.net_income) : "—"}
            subtext={
              netIncomeMoM !== null ? (
                <span className="flex items-center gap-1">
                  {netIncomeMoM >= 0 ? (
                    <ArrowUp className="h-3 w-3 text-favorable-fg" />
                  ) : (
                    <ArrowDown className="h-3 w-3 text-severity-high-fg" />
                  )}
                  <span className={cn("font-data", netIncomeMoM >= 0 ? "text-favorable-fg" : "text-severity-high-fg")} data-numeric>
                    {Math.abs(netIncomeMoM).toFixed(1)}% MoM
                  </span>
                </span>
              ) : (
                latestFinancials ? `${latestFinancials.net_margin_pct.toFixed(1)}% margin` : "—"
              )
            }
            icon={<DollarSign className="h-4 w-4" />}
          />

          {/* OpEx */}
          <MetricCard
            label="Operating Expenses"
            value={latestFinancials ? formatCurrency(latestFinancials.opex) : "—"}
            subtext={
              latestFinancials
                ? `${((latestFinancials.opex / latestFinancials.revenue) * 100).toFixed(1)}% of revenue`
                : "—"
            }
            icon={<DollarSign className="h-4 w-4" />}
          />

          {/* Critical Anomalies */}
          <MetricCard
            label="Critical Issues"
            value={criticalAnomalyCount}
            subtext={
              criticalAnomalyCount > 0
                ? `${criticalAnomalyCount} high/medium ${criticalAnomalyCount === 1 ? "anomaly" : "anomalies"}`
                : "No critical anomalies"
            }
            icon={<AlertTriangle className="h-4 w-4" />}
          />

          {/* Health Indicator */}
          <MetricCard
            label="Financial Health"
            value={
              latestFinancials
                ? latestFinancials.net_income >= 0
                  ? "Profitable"
                  : "Burning"
                : "—"
            }
            subtext={
              latestFinancials && latestFinancials.net_income < 0
                ? `${formatCurrency(Math.abs(latestFinancials.net_income))}/mo burn`
                : latestFinancials
                ? `${latestFinancials.net_margin_pct.toFixed(1)}% net margin`
                : "No data"
            }
            icon={<TrendingUp className="h-4 w-4" />}
          />
        </div>

        {/* Recent reports */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">
              Recent reports
            </h2>
            
            {/* Tabs */}
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab("monthly")}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === "monthly"
                    ? "bg-accent text-white"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface"
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setActiveTab("quarterly")}
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
          
          <HistoryList reports={reports} loading={reportsLoading} />
        </div>
      </div>
    </div>
  );
}
