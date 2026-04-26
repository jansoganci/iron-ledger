import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  AlertTriangle,
  AlertCircle,
  RefreshCw,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { apiFetch } from "../lib/api";
import { useCompany } from "../hooks/useCompany";
import { QuarterlyProgress } from "../components/QuarterlyProgress";
import { AnomalyCard } from "../components/AnomalyCard";
import { formatCurrency } from "../lib/formatters";
import { cn } from "../lib/utils";

interface QuarterlyStatusResponse {
  status: "running" | "complete" | "failed";
  progress_pct: number;
  step_label: string;
  result?: QuarterlyResult;
  error?: {
    error_type: "timeout" | "guardrail_failed" | "empty_data" | "internal";
    message: string;
  };
}

interface QuarterlyResult {
  narrative: string;
  numbers_used: number[];
  kpis: {
    revenue: number;
    gross_margin: number;
    opex: number;
    yoy_revenue_pct?: number | null;
    yoy_gross_margin_delta?: number | null;
    yoy_opex_pct?: number | null;
  };
  missing_months: string[];
  yoy_deltas: {
    py_revenue: number;
    py_gross_margin: number;
    py_opex: number;
    yoy_revenue_pct: number;
    yoy_gross_margin_delta: number;
    yoy_opex_pct: number;
  } | null;
  anomalies_grouped: {
    recurring: AnomalyGroup[];
    persistent: AnomalyGroup[];
    oneOff: AnomalyGroup[];
  };
}

interface AnomalyGroup {
  account_id: string;
  account_name: string;
  recurrence_count: number;
  monthly_details: {
    month: string;
    variance_pct: number | null;
    severity: string;
  }[];
  trend: string;
}

const QUARTER_LABELS: Record<number, string> = {
  1: "Q1",
  2: "Q2",
  3: "Q3",
  4: "Q4",
};

const ERROR_MESSAGES: Record<string, { title: string; description: string; cta: string }> = {
  timeout: {
    title: "This is taking longer than expected",
    description:
      "The Claude API may be slow right now. Please try again in a moment.",
    cta: "Try Again",
  },
  guardrail_failed: {
    title: "We couldn't verify the report's numbers",
    description: "This usually resolves on a retry.",
    cta: "Try Again",
  },
  empty_data: {
    title: "Not enough months uploaded",
    description:
      "Upload at least 2 months for this quarter to generate a quarterly summary.",
    cta: "Go to Reports",
  },
  internal: {
    title: "Something went wrong",
    description: "Please try again or contact support if the issue persists.",
    cta: "Try Again",
  },
};

export default function QuarterlyReportPage() {
  const { yearQuarter } = useParams<{ yearQuarter: string }>();
  const navigate = useNavigate();
  const { data: company } = useCompany();

  const [year, quarter] = (yearQuarter ?? "").split("-Q").map(Number);
  const [jobId, setJobId] = useState<string | null>(null);
  const [persistedReport, setPersistedReport] = useState<{
    result: QuarterlyResult;
    is_stale: boolean;
    generated_at: string | null;
  } | null>(null);

  // Fetch persisted report from DB on mount
  const { data: dbReport, isLoading: isLoadingDbReport } = useQuery({
    queryKey: ["quarterly-report", company?.id, year, quarter],
    queryFn: () =>
      apiFetch<{
        report_id: string;
        year: number;
        quarter: number;
        is_stale: boolean;
        generated_at: string | null;
        result: QuarterlyResult;
      }>(`/report/${company!.id}/quarterly/${year}/${quarter}`),
    enabled: !!company?.id && !!year && !!quarter,
    retry: false,
  });

  useEffect(() => {
    if (dbReport?.result) {
      setPersistedReport({
        result: dbReport.result,
        is_stale: dbReport.is_stale,
        generated_at: dbReport.generated_at,
      });
    }
  }, [dbReport]);

  const { data: statusData, refetch: refetchStatus } = useQuery<QuarterlyStatusResponse>({
    queryKey: ["quarterly-status", jobId],
    queryFn: () =>
      apiFetch<QuarterlyStatusResponse>(
        `/report/${company!.id}/quarterly/${year}/${quarter}/status/${jobId}`
      ),
    enabled: !!jobId && !!company?.id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "running") return 1000; // Poll every 1 second
      return false;
    },
  });

  // When generation completes, set the persisted report
  useEffect(() => {
    if (statusData?.status === "complete" && statusData.result) {
      setPersistedReport({
        result: statusData.result,
        is_stale: false,
        generated_at: new Date().toISOString(),
      });
    }
  }, [statusData]);

  const handleGenerate = async () => {
    if (!company?.id) return;

    try {
      const response = await apiFetch<{ job_id: string; status: string; progress_pct: number }>(
        `/report/${company.id}/quarterly/${year}/${quarter}/generate`,
        { method: "POST" }
      );
      setJobId(response.job_id);
      // Now using DB persistence
    } catch (error) {
      console.error("Failed to start quarterly generation:", error);
    }
  };

  const handleRegenerate = async () => {
    if (!company?.id) return;
    setPersistedReport(null);
    setJobId(null);
    try {
      await apiFetch(`/report/${company.id}/quarterly/${year}/${quarter}`, {
        method: "DELETE",
      });
    } catch {
      // Idempotent — 404 is fine (no persisted report to delete)
    }
    handleGenerate();
  };

  if (!year || !quarter || quarter < 1 || quarter > 4) {
    return (
      <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
        <div className="max-w-2xl mx-auto text-center space-y-4">
          <AlertCircle className="h-12 w-12 text-severity-high-fg mx-auto" />
          <h1 className="text-2xl font-bold">Invalid quarter</h1>
          <p className="text-text-secondary">Please check the URL and try again.</p>
          <Link
            to="/reports"
            className="inline-flex items-center gap-2 text-accent hover:underline"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Reports
          </Link>
        </div>
      </div>
    );
  }

  const result = statusData?.result ?? persistedReport?.result;

  // Loading state
  if (jobId && statusData?.status === "running") {
    return (
      <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
        <div className="max-w-2xl mx-auto">
          <QuarterlyProgress
            progressPct={statusData.progress_pct}
            stepLabel={statusData.step_label}
          />
        </div>
      </div>
    );
  }

  // Error state
  if (jobId && statusData?.status === "failed" && statusData.error) {
    const errorConfig = ERROR_MESSAGES[statusData.error.error_type] ?? ERROR_MESSAGES.internal;

    return (
      <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
        <div className="max-w-2xl mx-auto space-y-5">
          <Link
            to="/reports"
            className="inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Reports
          </Link>

          <div className="rounded-lg border border-severity-high-fg bg-severity-high-bg p-6 space-y-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-6 w-6 text-severity-high-fg shrink-0 mt-0.5" />
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-text-primary">
                  {errorConfig.title}
                </h2>
                <p className="text-sm text-text-secondary">{statusData.error.message}</p>
              </div>
            </div>

            <div className="flex gap-3">
              {statusData.error.error_type === "empty_data" ? (
                <button
                  onClick={() => navigate("/reports")}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                >
                  {errorConfig.cta}
                </button>
              ) : (
                <button
                  onClick={handleRegenerate}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  {errorConfig.cta}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Empty state - no result yet (and not loading from DB)
  if (!result && !isLoadingDbReport) {
    return (
      <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
        <div className="max-w-2xl mx-auto space-y-5">
          <Link
            to="/reports"
            className="inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Reports
          </Link>

          <div className="text-center space-y-4 py-12">
            <h1 className="text-2xl font-semibold text-text-primary">
              {QUARTER_LABELS[quarter]} {year} Summary
            </h1>
            <p className="text-text-secondary">
              Generate a quarterly summary report for {QUARTER_LABELS[quarter]} {year}
            </p>
            <button
              onClick={handleGenerate}
              className="px-6 py-3 bg-accent text-white rounded-lg hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            >
              Generate Quarterly Summary
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Success state - show report (should always have result here due to earlier checks)
  if (!result) {
    return null; // Should never reach here
  }

  return (
    <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5 pb-8">
        {/* Breadcrumb */}
        <div className="flex items-center justify-between">
          <Link
            to="/reports"
            className="inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            <ArrowLeft className="h-4 w-4" />
            Reports
          </Link>
          <button
            onClick={handleRegenerate}
            className="text-sm text-accent hover:underline flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            <RefreshCw className="h-3 w-3" />
            Regenerate
          </button>
        </div>

        <h1 className="text-2xl font-semibold text-text-primary">
          {QUARTER_LABELS[quarter]} {year} Summary
        </h1>

        {/* Stale banner */}
        {persistedReport?.is_stale && (
          <div className="rounded-lg border border-severity-medium-border bg-severity-medium-bg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3 flex-1">
                <AlertTriangle className="h-5 w-5 text-severity-medium-fg shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium text-text-primary">
                    Monthly data was updated after this report was generated
                  </p>
                  <p className="text-sm text-text-secondary">
                    Regenerate for the latest figures.
                  </p>
                </div>
              </div>
              <button
                onClick={handleRegenerate}
                className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 hover:scale-[1.015] active:scale-[0.97] transition-all text-sm font-medium shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
              >
                Regenerate
              </button>
            </div>
          </div>
        )}

        {/* Missing months banner */}
        {result.missing_months.length > 0 && (
          <div className="rounded-lg border border-severity-medium-border bg-severity-medium-bg p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-severity-medium-fg shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-text-primary">
                  Note: Data for some months is not available
                </p>
                <p className="text-text-secondary mt-1">
                  This summary covers only the months with uploaded data. Missing:{" "}
                  {result.missing_months.map((d) => new Date(d).toLocaleDateString("en-US", { month: "short" })).join(", ")}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-lg border border-border bg-surface px-5 py-4 shadow-sm space-y-2">
            <p className="text-[11px] font-medium text-text-secondary uppercase tracking-widest">Revenue</p>
            <div className="font-hero-num text-2xl font-semibold text-text-primary">{formatCurrency(result.kpis.revenue)}</div>
            {result.kpis.yoy_revenue_pct != null && (
              <div className="flex items-center gap-1 text-sm">
                {result.kpis.yoy_revenue_pct >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-favorable-fg" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-severity-high-fg" />
                )}
                <span
                  className={cn(
                    "font-medium",
                    result.kpis.yoy_revenue_pct >= 0
                      ? "text-favorable-fg"
                      : "text-severity-high-fg"
                  )}
                >
                  {result.kpis.yoy_revenue_pct >= 0 ? "+" : ""}
                  {result.kpis.yoy_revenue_pct.toFixed(1)}% YoY
                </span>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-surface px-5 py-4 shadow-sm space-y-2">
            <p className="text-[11px] font-medium text-text-secondary uppercase tracking-widest">Gross Margin</p>
            <div className="font-hero-num text-2xl font-semibold text-text-primary">{result.kpis.gross_margin.toFixed(1)}%</div>
            {result.kpis.yoy_gross_margin_delta != null && (
              <div className="flex items-center gap-1 text-sm">
                {result.kpis.yoy_gross_margin_delta >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-favorable-fg" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-severity-high-fg" />
                )}
                <span
                  className={cn(
                    "font-medium",
                    result.kpis.yoy_gross_margin_delta >= 0
                      ? "text-favorable-fg"
                      : "text-severity-high-fg"
                  )}
                >
                  {result.kpis.yoy_gross_margin_delta >= 0 ? "+" : ""}
                  {result.kpis.yoy_gross_margin_delta.toFixed(1)}pp YoY
                </span>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-surface px-5 py-4 shadow-sm space-y-2">
            <p className="text-[11px] font-medium text-text-secondary uppercase tracking-widest">OpEx</p>
            <div className="font-hero-num text-2xl font-semibold text-text-primary">{formatCurrency(result.kpis.opex)}</div>
            {result.kpis.yoy_opex_pct != null && (
              <div className="flex items-center gap-1 text-sm">
                {result.kpis.yoy_opex_pct >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-severity-high-fg" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-favorable-fg" />
                )}
                <span
                  className={cn(
                    "font-medium",
                    result.kpis.yoy_opex_pct <= 0
                      ? "text-favorable-fg"
                      : "text-severity-high-fg"
                  )}
                >
                  {result.kpis.yoy_opex_pct >= 0 ? "+" : ""}
                  {result.kpis.yoy_opex_pct.toFixed(1)}% YoY
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Narrative */}
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="px-6 py-4 border-b border-border">
            <div className="flex items-center gap-3">
              <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
                Quarterly Summary
              </h2>
              <div className="flex-1 h-px bg-border" />
            </div>
          </div>
          <div className="px-8 py-7 font-serif">
            <QuarterlyNarrativeBlock text={result.narrative} />
          </div>
        </div>

        {/* Anomalies */}
        {(result.anomalies_grouped.recurring.length > 0 ||
          result.anomalies_grouped.persistent.length > 0 ||
          result.anomalies_grouped.oneOff.length > 0) && (
          <div className="rounded-xl border border-border bg-surface overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
                  Cross-Quarter Anomalies
                </h2>
                <div className="flex-1 h-px bg-border" />
              </div>
            </div>
            <div className="px-6 py-5 space-y-5">
            {/* Recurring (3/3 months) */}
            {result.anomalies_grouped.recurring.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold text-severity-high-fg uppercase tracking-widest flex items-center gap-2">
                  <span className="w-1 h-4 bg-severity-high-fg rounded-full inline-block"></span>
                  Recurring Issues (3/3 months)
                </p>
                <div className="space-y-3">
                  {result.anomalies_grouped.recurring.map((anomaly) => (
                    <div
                      key={anomaly.account_id}
                      className="rounded-lg border-l-4 border-severity-high-fg bg-surface p-4"
                    >
                      <div className="space-y-2">
                        <h4 className="font-semibold text-text-primary">
                          {anomaly.account_name}
                        </h4>
                        <p className="text-sm text-text-secondary">
                          Flagged {anomaly.recurrence_count}/3 months •{" "}
                          {anomaly.monthly_details
                            .map((d) => `${d.month.charAt(0).toUpperCase() + d.month.slice(1)} ${d.variance_pct != null ? (d.variance_pct >= 0 ? "+" : "") + d.variance_pct.toFixed(1) + "%" : "—"}`)
                            .join(" • ")}{" "}
                          • trend: {anomaly.trend}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Persistent (2/3 months) */}
            {result.anomalies_grouped.persistent.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold text-severity-medium-fg uppercase tracking-widest flex items-center gap-2">
                  <span className="w-1 h-4 bg-severity-medium-fg rounded-full inline-block"></span>
                  Persistent Issues (2/3 months)
                </p>
                <div className="space-y-3">
                  {result.anomalies_grouped.persistent.map((anomaly) => (
                    <div
                      key={anomaly.account_id}
                      className="rounded-lg border-l-4 border-severity-medium-fg bg-surface p-4"
                    >
                      <div className="space-y-2">
                        <h4 className="font-semibold text-text-primary">
                          {anomaly.account_name}
                        </h4>
                        <p className="text-sm text-text-secondary">
                          Flagged {anomaly.recurrence_count}/3 months •{" "}
                          {anomaly.monthly_details
                            .map((d) => `${d.month.charAt(0).toUpperCase() + d.month.slice(1)} ${d.variance_pct != null ? (d.variance_pct >= 0 ? "+" : "") + d.variance_pct.toFixed(1) + "%" : "—"}`)
                            .join(" • ")}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* One-Off (1/3 months) */}
            {result.anomalies_grouped.oneOff.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-widest flex items-center gap-2">
                  <span className="w-1 h-4 bg-amber-500 rounded-full inline-block"></span>
                  One-Off Anomalies (1/3 months)
                </p>
                <div className="space-y-3">
                  {result.anomalies_grouped.oneOff.map((anomaly) => (
                    <div
                      key={anomaly.account_id}
                      className="rounded-lg border-l-4 border-amber-500 bg-surface p-4"
                    >
                      <div className="space-y-2">
                        <h4 className="font-semibold text-text-primary">
                          {anomaly.account_name}
                        </h4>
                        <p className="text-sm text-text-secondary">
                          {anomaly.monthly_details
                            .map((d) => `${d.month.charAt(0).toUpperCase() + d.month.slice(1)} ${d.variance_pct != null ? (d.variance_pct >= 0 ? "+" : "") + d.variance_pct.toFixed(1) + "%" : "—"}`)
                            .join(" • ")}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            </div>
          </div>
        )}

        {/* Year-over-Year (only if data exists) */}
        {result.yoy_deltas && (
          <div className="rounded-xl border border-border bg-surface overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
                  Year-over-Year Comparison
                </h2>
                <div className="flex-1 h-px bg-border" />
              </div>
            </div>
            <div className="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-text-secondary mb-2">
                  {QUARTER_LABELS[quarter]} {year - 1}:
                </p>
                <ul className="space-y-1 text-text-primary font-data">
                  <li>{formatCurrency(result.yoy_deltas.py_revenue)} revenue</li>
                  <li>{result.yoy_deltas.py_gross_margin.toFixed(1)}% margin</li>
                  <li>{formatCurrency(result.yoy_deltas.py_opex)} OpEx</li>
                </ul>
              </div>
              <div>
                <p className="text-text-secondary mb-2">
                  {QUARTER_LABELS[quarter]} {year}:
                </p>
                <ul className="space-y-1 text-text-primary font-data">
                  <li>{formatCurrency(result.kpis.revenue)} revenue</li>
                  <li>{result.kpis.gross_margin.toFixed(1)}% margin</li>
                  <li>{formatCurrency(result.kpis.opex)} OpEx</li>
                </ul>
              </div>
            </div>
            <div className="pt-4 border-t border-border">
              <p className="text-sm text-text-secondary">
                → Revenue{" "}
                <span
                  className={cn(
                    "font-medium",
                    result.yoy_deltas.yoy_revenue_pct >= 0
                      ? "text-favorable-fg"
                      : "text-severity-high-fg"
                  )}
                >
                  {result.yoy_deltas.yoy_revenue_pct >= 0 ? "+" : ""}
                  {result.yoy_deltas.yoy_revenue_pct.toFixed(1)}%
                </span>{" "}
                • Margin{" "}
                <span
                  className={cn(
                    "font-medium",
                    result.yoy_deltas.yoy_gross_margin_delta >= 0
                      ? "text-favorable-fg"
                      : "text-severity-high-fg"
                  )}
                >
                  {result.yoy_deltas.yoy_gross_margin_delta >= 0 ? "+" : ""}
                  {result.yoy_deltas.yoy_gross_margin_delta.toFixed(1)}pp
                </span>{" "}
                • OpEx{" "}
                <span
                  className={cn(
                    "font-medium",
                    result.yoy_deltas.yoy_opex_pct <= 0
                      ? "text-favorable-fg"
                      : "text-severity-high-fg"
                  )}
                >
                  {result.yoy_deltas.yoy_opex_pct >= 0 ? "+" : ""}
                  {result.yoy_deltas.yoy_opex_pct.toFixed(1)}%
                </span>
              </p>
            </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Markdown-aware narrative renderer for quarterly reports.
// Handles **Section Header** lines, **inline bold**, and - bullet items.
// ---------------------------------------------------------------------------

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i} className="font-semibold text-text-primary">
        {part.slice(2, -2)}
      </strong>
    ) : (
      part
    )
  );
}

function QuarterlyNarrativeBlock({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (!listBuffer.length) return;
    elements.push(
      <ul key={elements.length} className="space-y-1.5 my-3 pl-1">
        {listBuffer.map((item, i) => (
          <li key={i} className="flex gap-2 text-[15px] leading-relaxed text-text-primary">
            <span className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-text-secondary/50" />
            <span>{renderInline(item)}</span>
          </li>
        ))}
      </ul>
    );
    listBuffer = [];
  };

  for (const raw of lines) {
    const trimmed = raw.trim();

    if (!trimmed) {
      flushList();
      continue;
    }

    // Full-line **Section Header**
    if (/^\*\*[^*]+\*\*$/.test(trimmed)) {
      flushList();
      const title = trimmed.slice(2, -2);
      elements.push(
        <div key={elements.length} className="flex items-center gap-3 mt-7 mb-3 first:mt-0">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-text-secondary whitespace-nowrap">
            {title}
          </h3>
          <div className="flex-1 h-px bg-border" />
        </div>
      );
      continue;
    }

    // Bullet list item: "- " or "• "
    const bulletMatch = trimmed.match(/^[-•]\s+(.+)$/);
    if (bulletMatch) {
      listBuffer.push(bulletMatch[1]);
      continue;
    }

    // Regular paragraph
    flushList();
    elements.push(
      <p key={elements.length} className="text-[15px] leading-relaxed text-text-primary my-2">
        {renderInline(trimmed)}
      </p>
    );
  }

  flushList();
  return <>{elements}</>;
}
