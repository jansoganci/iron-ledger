import { useParams, useNavigate, useLocation, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, ChevronDown, ChevronRight, Database, TrendingUp, X } from "lucide-react";
import { apiFetch } from "../lib/api";
import { useCompany } from "../hooks/useCompany";
import { ReportSummary } from "../components/ReportSummary";
import type { OpusStatus } from "../components/ReportSummary";
import { AnomalyCard, AnomalyCardData, AnomalyCardSkeleton } from "../components/AnomalyCard";
import { MailButton } from "../components/MailButton";
import {
  MappingConfirmPanel,
  LowConfidenceColumn,
} from "../components/MappingConfirmPanel";
import type { ReconciliationItem } from "../components/ReconciliationCard";
import { useState, useEffect, useRef } from "react";

const CATEGORY_ORDER = [
  "REVENUE",
  "COGS",
  "OPEX",
  "G&A",
  "R&D",
  "OTHER_INCOME",
  "OTHER",
];

const CATEGORY_LABELS: Record<string, string> = {
  REVENUE: "Revenue",
  COGS: "Cost of goods sold",
  OPEX: "Operating expenses",
  "G&A": "General & administrative",
  "R&D": "Research & development",
  OTHER_INCOME: "Other income",
  OTHER: "Other",
};

interface AnomalyResponse extends AnomalyCardData {}

interface Financials {
  revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  opex: number;
  net_income: number;
  net_margin_pct: number;
}

interface ReportResponse {
  report_id: string;
  company_id: string;
  period: string;
  generated_at: string | null;
  summary: string;
  anomaly_count: number;
  error_count: number;
  is_stale: boolean;
  opus_upgraded: boolean;
  anomalies: AnomalyResponse[];
  reconciliations: ReconciliationItem[] | null;
  financials: Financials | null;
}

interface RunStatusResponse {
  run_id: string;
  status: string;
  opus_status: OpusStatus;
}

interface NavState {
  runId?: string;
  lowConfidenceColumns?: LowConfidenceColumn[];
}

const SEVERITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

export default function ReportPage() {
  const { period } = useParams<{ period: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state ?? {}) as NavState;
  const runId = navState.runId;
  const initialLowConf = navState.lowConfidenceColumns ?? [];

  const [mappingDismissed, setMappingDismissed] = useState(false);
  const [quarterlyBannerDismissed, setQuarterlyBannerDismissed] = useState(false);
  const [opusStatus, setOpusStatus] = useState<OpusStatus | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef<number>(Date.now());

  const { data: company, isLoading: companyLoading } = useCompany();

  const { data: report, isLoading: reportLoading, error, refetch: refetchReport } = useQuery<ReportResponse>({
    queryKey: ["report", company?.id, period],
    queryFn: () =>
      apiFetch<ReportResponse>(`/report/${company!.id}/${period}`),
    enabled: !!company?.id && !!period,
  });

  // Poll opus_status while run_id is known and upgrade is in flight.
  useEffect(() => {
    if (!runId) return;

    const POLL_MS = 3_000;
    const TIMEOUT_MS = 90_000;

    const stop = () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };

    pollingRef.current = setInterval(async () => {
      const elapsed = Date.now() - startedAt.current;
      if (elapsed >= TIMEOUT_MS) {
        stop();
        setOpusStatus((prev) => (prev === "pending" || prev === "running" ? "failed" : prev));
        return;
      }

      try {
        const data = await apiFetch<RunStatusResponse>(`/runs/${runId}/status`);
        setOpusStatus(data.opus_status);
        if (data.opus_status === "done") {
          stop();
          refetchReport();
        } else if (data.opus_status === "failed") {
          stop();
        }
      } catch {
        // network hiccup — keep polling
      }
    }, POLL_MS);

    return stop;
  }, [runId, refetchReport]);

  const isLoading = companyLoading || reportLoading;

  if (error) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center px-4">
        <div
          role="alert"
          className="max-w-md w-full rounded-lg border border-severity-high-fg bg-severity-high-bg text-severity-high-fg p-6 space-y-4"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0" aria-hidden />
            <div className="space-y-1">
              <h2 className="text-base font-semibold">
                This report failed verification
              </h2>
              <p className="text-sm">
                Go back to upload to retry.
              </p>
            </div>
          </div>
          <Link
            to="/upload"
            className="block w-full text-center rounded-md bg-severity-high-fg px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-severity-high-fg focus:ring-offset-2"
          >
            Go to upload
          </Link>
        </div>
      </div>
    );
  }

  const sortedAnomalies = report
    ? [...report.anomalies].sort(
        (a, b) =>
          (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
      )
    : [];

  // Group anomalies by account category, preserving severity ordering within each group.
  const byCategory: Record<string, AnomalyCardData[]> = {};
  for (const a of sortedAnomalies) {
    const key = a.category || "OTHER";
    (byCategory[key] ??= []).push(a);
  }
  const knownCategories = new Set(CATEGORY_ORDER);
  const categoriesToRender = [
    ...CATEGORY_ORDER.filter((c) => byCategory[c]?.length),
    ...Object.keys(byCategory).filter((c) => !knownCategories.has(c)),
  ];

  const showMappingPanel =
    !mappingDismissed && runId && initialLowConf.length > 0;

  // Check if this is a quarter-end month (Mar/Jun/Sep/Dec) to show quarterly banner
  const isQuarterEnd = () => {
    if (!period) return false;
    const month = parseInt(period.split("-")[1]);
    return [3, 6, 9, 12].includes(month);
  };

  const getQuarterInfo = () => {
    if (!period) return { year: 0, quarter: 0 };
    const [year, month] = period.split("-").map(Number);
    return { year, quarter: Math.ceil(month / 3) };
  };

  const showQuarterlyBanner = !quarterlyBannerDismissed && isQuarterEnd() && report;

  return (
    <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5 pb-8">
        {/* Top nav row: back button left, actions right */}
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => navigate("/upload")}
            className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            New upload
          </button>

          {report && (
            <div className="flex items-center gap-2">
              <MailButton
                reportId={report.report_id}
                summary={report.summary}
                companyName={company?.name ?? ""}
                period={report.period}
                anomalyCount={report.anomaly_count}
              />
              <button
                onClick={() => {
                  const [year, month] = report.period.split("-");
                  navigate(`/data?year=${year}&month=${month}`);
                }}
                className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-text-primary hover:bg-canvas transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <Database className="h-4 w-4" aria-hidden />
                View data
              </button>
            </div>
          )}
        </div>

        {/* Quarterly Summary Banner */}
        {showQuarterlyBanner && (
          <div className="rounded-lg border border-accent/30 bg-accent/10 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3 flex-1">
                <TrendingUp className="h-5 w-5 text-accent shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium text-text-primary">
                    Q{getQuarterInfo().quarter} {getQuarterInfo().year} is complete
                  </p>
                  <p className="text-sm text-text-secondary">
                    Generate a quarterly summary to see trends across the quarter
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const { year, quarter } = getQuarterInfo();
                    navigate(`/report/quarterly/${year}-Q${quarter}`);
                  }}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all text-sm font-medium shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                >
                  Generate Quarterly Summary
                </button>
                <button
                  onClick={() => setQuarterlyBannerDismissed(true)}
                  className="p-2 text-text-secondary hover:text-text-primary rounded-lg hover:bg-surface transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  aria-label="Dismiss"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Report summary / skeleton */}
        {isLoading ? (
          <ReportSummary
            summary=""
            period={period ?? ""}
            generatedAt={null}
            anomalyCount={0}
            companyName={company?.name ?? ""}
            status="verified"
            isGenerating
          />
        ) : report ? (
          <ReportSummary
            summary={report.summary}
            period={report.period}
            generatedAt={report.generated_at}
            anomalyCount={report.anomaly_count}
            companyName={company?.name ?? ""}
            status={report.is_stale ? "stale" : "verified"}
            opusStatus={opusStatus}
            opusUpgraded={report.opus_upgraded}
            financials={report.financials}
            onRegenerate={() => navigate(`/upload?period=${report.period}`)}
            reconciliations={report.reconciliations}
            excelDownloadUrl={`/report/${report.company_id}/${report.period}/export.xlsx`}
          />
        ) : null}

        {/* Anomaly cards — grouped by category, 2-col on xl, 1-col below */}
        {isLoading ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {[0, 1, 2].map((i) => (
              <AnomalyCardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <>
            {categoriesToRender.length > 0 && (
              <div className="rounded-xl border border-border bg-surface overflow-hidden">
                <div className="px-6 py-4 border-b border-border">
                  <div className="flex items-center gap-3">
                    <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
                      Account Variance
                    </h2>
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-xs text-text-secondary">{sortedAnomalies.length} account{sortedAnomalies.length !== 1 ? "s" : ""}</span>
                  </div>
                </div>
                <div className="px-6 py-5 space-y-5">
                  {categoriesToRender.map((cat) => {
                    const items = byCategory[cat];
                    const flagged = items.filter(a => a.severity === "high" || a.severity === "medium");
                    const normal = items.filter(a => a.severity === "low");
                    const label = CATEGORY_LABELS[cat] ?? cat;
                    return (
                      <section key={cat} className="space-y-2">
                        <p className="text-xs font-semibold text-text-secondary uppercase tracking-widest">
                          {label}
                        </p>
                        {flagged.length > 0 && (
                          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                            {flagged.map((a, i) => (
                              <AnomalyCard key={`${a.account}-${i}`} {...a} />
                            ))}
                          </div>
                        )}
                        {flagged.length === 0 && normal.length > 0 && (
                          <CategoryAllNormalRow items={normal} />
                        )}
                      </section>
                    );
                  })}
                </div>
              </div>
            )}

            {sortedAnomalies.length === 0 && report && (
              <div className="rounded-xl border border-border bg-surface px-6 py-8 text-center space-y-1">
                <p className="text-favorable-fg font-semibold">No anomalies this period.</p>
                <p className="text-sm text-text-secondary">
                  Every account is within expected range vs. your history.
                </p>
              </div>
            )}
          </>
        )}

        {/* Mapping confirm panel — post-hoc, non-blocking */}
        {showMappingPanel && (
          <MappingConfirmPanel
            runId={runId!}
            columns={initialLowConf}
            onConfirmed={() => setMappingDismissed(true)}
          />
        )}
      </div>
    </div>
  );
}

function CategoryAllNormalRow({ items }: { items: AnomalyCardData[] }) {
  const [expanded, setExpanded] = useState(false);
  const count = items.length;
  return (
    <div className="rounded-lg border border-border bg-severity-normal-bg text-severity-normal-fg">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full flex items-center gap-2 px-4 py-3 text-sm text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-lg"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0" aria-hidden />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        )}
        <span className="text-favorable-fg" aria-hidden>✅</span>
        <span className="flex-1">
          All {count} item{count !== 1 ? "s" : ""} within normal range
        </span>
        <span className="text-xs underline underline-offset-2">
          {expanded ? "Hide details" : "Show details"}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border bg-surface p-3">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {items.map((a, i) => (
              <AnomalyCard key={`${a.account}-${i}`} {...a} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
