import {
  AlertTriangle,
  CheckCircle,
  Download,
  Loader2,
  RefreshCw,
  Sparkles,
  FileText,
} from "lucide-react";
import { formatPeriod, formatCurrency } from "../lib/formatters";
import { ReconciliationPanel } from "./ReconciliationPanel";
import type { ReconciliationItem } from "./ReconciliationCard";
import { cn } from "../lib/utils";

export type ReportStatus = "verified" | "stale" | "guardrail_failed";
export type OpusStatus = "pending" | "running" | "done" | "failed";

export interface Financials {
  revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  opex: number;
  net_income: number;
  net_margin_pct: number;
}

interface ReportSummaryProps {
  summary: string;
  period: string;
  generatedAt: string | null;
  anomalyCount: number;
  companyName: string;
  status: ReportStatus;
  isGenerating?: boolean;
  opusStatus?: OpusStatus | null;
  opusUpgraded?: boolean;
  financials?: Financials | null;
  onRegenerate?: () => void;
  reconciliations?: ReconciliationItem[] | null;
  excelDownloadUrl?: string;
}

// ---------------------------------------------------------------------------
// Narrative parser
// ---------------------------------------------------------------------------

interface NarrativePart {
  title: string;
  lines: string[];
}

function parseNarrative(text: string): NarrativePart[] {
  const parts: NarrativePart[] = [];
  // Split on "Part N —" or "Part N -" headers
  const sections = text.split(/(?=Part\s+\d+\s*[—–-])/i);
  for (const section of sections) {
    const trimmed = section.trim();
    if (!trimmed) continue;
    const headerMatch = trimmed.match(/^(Part\s+\d+\s*[—–-][^\n]*)\n?([\s\S]*)$/i);
    if (headerMatch) {
      parts.push({
        title: headerMatch[1].trim(),
        lines: headerMatch[2].trim().split("\n"),
      });
    } else {
      parts.push({ title: "", lines: trimmed.split("\n") });
    }
  }
  return parts.length ? parts : [{ title: "", lines: text.split("\n") }];
}

function NarrativeBlock({ lines }: { lines: string[] }) {
  const elements: React.ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length === 0) return;
    elements.push(
      <ul key={elements.length} className="space-y-1.5 my-3 pl-1">
        {listBuffer.map((item, i) => (
          <li key={i} className="flex gap-2 text-[15px] leading-relaxed text-text-primary">
            <span className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-text-secondary/50" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    );
    listBuffer = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const trimmed = raw.trim();

    if (!trimmed) {
      flushList();
      continue;
    }

    // Sub-section headers like "High severity:", "Flagged items:", etc.
    if (/^(high|medium|low)\s+severity\s*:?$/i.test(trimmed)) {
      flushList();
      const colorMap: Record<string, string> = {
        high: "text-severity-high-fg",
        medium: "text-severity-medium-fg",
        low: "text-text-secondary",
      };
      const level = trimmed.toLowerCase().replace(/\s+severity.*/, "");
      elements.push(
        <p key={elements.length} className={cn("text-xs font-semibold uppercase tracking-widest mt-5 mb-2", colorMap[level] ?? "text-text-secondary")}>
          {trimmed.replace(/:$/, "")}
        </p>
      );
      continue;
    }

    // Numbered list items: "1. Account — ..."
    const numberedMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
    if (numberedMatch) {
      flushList();
      elements.push(
        <div key={elements.length} className="flex gap-3 my-2.5">
          <span className="font-data shrink-0 text-xs text-text-secondary/60 mt-[3px] w-4 text-right">
            {numberedMatch[1]}.
          </span>
          <p className="text-[15px] leading-relaxed text-text-primary">{numberedMatch[2]}</p>
        </div>
      );
      continue;
    }

    // Bullet list items: "- " or "• "
    const bulletMatch = trimmed.match(/^[-•]\s+(.+)$/);
    if (bulletMatch) {
      listBuffer.push(bulletMatch[1]);
      continue;
    }

    // Plain paragraph
    flushList();
    elements.push(
      <p key={elements.length} className="text-[15px] leading-relaxed text-text-primary my-2">
        {trimmed}
      </p>
    );
  }
  flushList();
  return <>{elements}</>;
}

// ---------------------------------------------------------------------------
// Financials strip
// ---------------------------------------------------------------------------

function FinancialsStrip({ f }: { f: Financials }) {
  const gmColor =
    f.gross_margin_pct >= 50 ? "text-favorable-fg"
    : f.gross_margin_pct >= 30 ? "text-text-primary"
    : "text-severity-medium-fg";

  const niColor = f.net_income >= 0 ? "text-favorable-fg" : "text-severity-high-fg";

  const tiles = [
    {
      label: "Revenue",
      value: formatCurrency(f.revenue),
      sub: null,
    },
    {
      label: "Gross Profit",
      value: <span className={gmColor}>{formatCurrency(f.gross_profit)}</span>,
      sub: <span className={gmColor}>{f.gross_margin_pct.toFixed(1)}% margin</span>,
    },
    {
      label: "Net Income",
      value: <span className={niColor}>{formatCurrency(f.net_income)}</span>,
      sub: <span className={niColor}>{f.net_margin_pct.toFixed(1)}% margin</span>,
    },
    {
      label: "Total OpEx",
      value: formatCurrency(f.opex),
      sub: null,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {tiles.map(({ label, value, sub }) => (
        <div
          key={label}
          className="rounded-lg border border-border bg-surface px-5 py-4 shadow-sm"
        >
          <p className="text-[11px] font-medium text-text-secondary uppercase tracking-widest mb-1.5">
            {label}
          </p>
          <p className="font-hero-num text-xl font-semibold text-text-primary">{value}</p>
          {sub && <p className="text-xs mt-0.5">{sub}</p>}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stats strip (unused — kept for reference)
// ---------------------------------------------------------------------------

function StatsStrip({ reconciliations, anomalyCount }: {
  reconciliations: ReconciliationItem[] | null | undefined;
  anomalyCount: number;
}) {
  const recons = reconciliations ?? [];
  const high = recons.filter(r => Math.abs(r.delta) >= 5000).length;
  const medium = recons.filter(r => Math.abs(r.delta) >= 500 && Math.abs(r.delta) < 5000).length;
  const low = recons.filter(r => Math.abs(r.delta) < 500 && Math.abs(r.delta) > 0).length;

  const stats = [
    { label: "Findings", value: recons.length, color: "text-text-primary" },
    { label: "High", value: high, color: high > 0 ? "text-severity-high-fg" : "text-text-secondary" },
    { label: "Medium", value: medium, color: medium > 0 ? "text-severity-medium-fg" : "text-text-secondary" },
    { label: "Low", value: low, color: "text-text-secondary" },
    { label: "Flagged accounts", value: anomalyCount, color: anomalyCount > 0 ? "text-severity-medium-fg" : "text-favorable-fg" },
  ];

  return (
    <div className="flex flex-wrap gap-px border border-border rounded-lg overflow-hidden bg-border">
      {stats.map(({ label, value, color }) => (
        <div key={label} className="flex-1 min-w-[80px] bg-surface px-4 py-3 text-center">
          <p className={cn("font-hero-num text-xl font-semibold", color)}>{value}</p>
          <p className="text-[11px] text-text-secondary mt-0.5 uppercase tracking-wide">{label}</p>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ReportSummary({
  summary,
  period,
  generatedAt,
  anomalyCount,
  companyName,
  status,
  isGenerating = false,
  opusStatus = null,
  opusUpgraded = false,
  financials = null,
  onRegenerate,
  reconciliations,
  excelDownloadUrl,
}: ReportSummaryProps) {
  const periodLabel = formatPeriod(period);

  if (status === "guardrail_failed") return null;

  if (isGenerating) {
    return (
      <div className="rounded-xl border border-border bg-surface p-8 space-y-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-text-primary">{companyName}</h1>
            <Loader2 className="h-5 w-5 text-accent animate-spin" />
          </div>
          <p className="text-sm text-text-secondary">Month-end Close Report · {periodLabel}</p>
        </div>
        <div className="space-y-2.5 animate-pulse">
          {[90, 85, 70, 55, 80, 60].map((w, i) => (
            <div key={i} className={`h-3 bg-severity-normal-bg rounded`} style={{ width: `${w}%` }} />
          ))}
        </div>
      </div>
    );
  }

  const isStale = status === "stale";
  const showOpusBanner = opusStatus === "pending" || opusStatus === "running";
  const narrativeParts = parseNarrative(summary);

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden">
      {/* Opus upgrade banner */}
      {showOpusBanner && (
        <div className="flex items-center gap-2 bg-accent/10 border-b border-accent/20 px-6 py-2.5 text-sm text-accent">
          <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
          <span>Advanced analysis in progress — your upgraded report will appear here shortly.</span>
        </div>
      )}

      {/* Stale warning */}
      {isStale && (
        <div className="flex items-center gap-2 bg-severity-medium-bg border-b border-severity-medium-fg/20 px-6 py-2.5 text-sm text-severity-medium-fg">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <p className="flex-1">
            This report was generated before the source file was re-uploaded.{" "}
            {onRegenerate && (
              <button type="button" onClick={onRegenerate}
                className="font-medium underline underline-offset-2 hover:no-underline focus:outline-none">
                <RefreshCw className="inline h-3 w-3 mr-0.5" />Regenerate
              </button>
            )}
          </p>
        </div>
      )}

      {/* Document header */}
      <div className="px-8 pt-8 pb-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <FileText className="h-4 w-4 text-text-secondary" aria-hidden />
              <span className="text-xs font-medium text-text-secondary uppercase tracking-widest">
                Month-end Close Report
              </span>
            </div>
            <h1 className="text-2xl font-semibold text-text-primary">{companyName}</h1>
            <p className="text-base text-text-secondary">{periodLabel}</p>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <div className="flex items-center gap-2 flex-wrap justify-end">
              {status === "verified" && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-favorable-bg text-favorable-fg px-3 py-1 text-xs font-semibold">
                  <CheckCircle className="h-3.5 w-3.5" />
                  Verified · Guardrail Passed
                </span>
              )}
              {opusUpgraded && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 text-accent px-3 py-1 text-xs font-semibold">
                  <Sparkles className="h-3.5 w-3.5" />
                  Advanced Analysis
                </span>
              )}
            </div>
            {generatedAt && (
              <p className="text-xs text-text-secondary">
                Generated {new Date(generatedAt).toLocaleString("en-US", {
                  month: "short", day: "numeric", year: "numeric",
                  hour: "numeric", minute: "2-digit",
                })}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* P&L KPI strip */}
      {financials && (
        <div className="px-8 pb-6">
          <FinancialsStrip f={financials} />
        </div>
      )}

      {/* Narrative — full report, serif body */}
      <div className="px-8 py-7">
        {narrativeParts.map((part, i) => (
          <div key={i} className={i > 0 ? "mt-8" : ""}>
            {part.title && (
              <div className="flex items-center gap-3 mb-4">
                <h2 className="text-xs font-semibold uppercase tracking-widest text-text-secondary">
                  {part.title}
                </h2>
                <div className="flex-1 h-px bg-border" />
              </div>
            )}
            <div className="font-serif">
              <NarrativeBlock lines={part.lines} />
            </div>
          </div>
        ))}
      </div>

      {/* Reconciliation findings */}
      {reconciliations && reconciliations.length > 0 && (
        <div className="px-8 pb-7 border-t border-border pt-6">
          <ReconciliationPanel reconciliations={reconciliations} />
        </div>
      )}

      {/* Footer actions */}
      <div className="px-8 py-4 border-t border-border bg-canvas flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-text-secondary">
          {status === "verified"
            ? "All numbers verified against source data by the numeric guardrail."
            : "Source data has changed since this report was generated."}
        </p>
        {excelDownloadUrl && (
          <a
            href={excelDownloadUrl}
            download
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <Download className="h-4 w-4" aria-hidden />
            Download Excel
          </a>
        )}
      </div>
    </div>
  );
}
