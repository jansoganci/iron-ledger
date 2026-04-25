import { useParams, useNavigate, useLocation, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, ChevronDown, ChevronRight, Database } from "lucide-react";
import { apiFetch } from "../lib/api";
import { useCompany } from "../hooks/useCompany";
import { ReportSummary } from "../components/ReportSummary";
import { AnomalyCard, AnomalyCardData, AnomalyCardSkeleton } from "../components/AnomalyCard";
import { MailButton } from "../components/MailButton";
import {
  MappingConfirmPanel,
  LowConfidenceColumn,
} from "../components/MappingConfirmPanel";
import type { ReconciliationItem } from "../components/ReconciliationCard";
import { useState } from "react";

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

interface ReportResponse {
  report_id: string;
  company_id: string;
  period: string;
  generated_at: string | null;
  summary: string;
  anomaly_count: number;
  error_count: number;
  is_stale: boolean;
  anomalies: AnomalyResponse[];
  reconciliations: ReconciliationItem[] | null;
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

  const { data: company, isLoading: companyLoading } = useCompany();

  const { data: report, isLoading: reportLoading, error } = useQuery<ReportResponse>({
    queryKey: ["report", company?.id, period],
    queryFn: () =>
      apiFetch<ReportResponse>(`/report/${company!.id}/${period}`),
    enabled: !!company?.id && !!period,
  });

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

  return (
    <div className="min-h-screen bg-canvas px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5 pb-8">
        {/* Back nav */}
        <button
          onClick={() => navigate("/upload")}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          New upload
        </button>

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
            onRegenerate={() => navigate(`/upload?period=${report.period}`)}
            reconciliations={report.reconciliations}
            excelDownloadUrl={`/report/${report.company_id}/${report.period}/export.xlsx`}
          />
        ) : null}

        {/* Actions */}
        {report && (
          <div className="flex gap-3">
            <MailButton reportId={report.report_id} />
            <button
              onClick={() => {
                const [year, month] = report.period.split("-");
                navigate(`/data?year=${year}&month=${month}`);
              }}
              className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <Database className="h-4 w-4" aria-hidden />
              View data for this period
            </button>
          </div>
        )}

        {/* Anomaly cards — grouped by category, 2-col on xl, 1-col below */}
        {isLoading ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {[0, 1, 2].map((i) => (
              <AnomalyCardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <>
            {categoriesToRender.map((cat) => {
              const items = byCategory[cat];
              const flagged = items.filter(
                (a) => a.severity === "high" || a.severity === "medium"
              );
              const normal = items.filter((a) => a.severity === "low");
              const label = CATEGORY_LABELS[cat] ?? cat;
              return (
                <section key={cat} className="space-y-2">
                  <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
                    {label}
                  </h2>
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

            {sortedAnomalies.length === 0 && report && (
              <div className="rounded-lg border border-favorable-bg bg-favorable-bg px-4 py-6 text-center space-y-1">
                <p className="text-favorable-fg font-semibold">No anomalies this period.</p>
                <p className="text-sm text-favorable-fg/80">
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
