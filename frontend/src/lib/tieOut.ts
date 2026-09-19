// Close-checklist grouping helpers. Needles match backend/tools/file_type.py.

export type TieOutGroupKey =
  | "payroll"
  | "supplier_invoices"
  | "contracts"
  | "other";

export type ControlStatus =
  | "tied_out"
  | "has_exceptions"
  | "mapping_required"
  | "source_missing"
  | "not_compared";

export interface ControlComparison {
  gl_account: string;
  supporting_amount: number | null;
  gl_amount: number | null;
  difference: number | null;
  classification?: string | null;
  complete: boolean;
  incomplete_reason?: string | null;
}

export interface ControlResult {
  key: "payroll" | "supplier_invoices" | "contracts";
  label: string;
  status: ControlStatus;
  source_file?: string | null;
  period?: string | null;
  amount_scope?: string | null;
  gl_targets: string[];
  mapping_mode: "row" | "file_total" | "none";
  comparisons: ControlComparison[];
  next_action: string;
  incomplete_reason?: string | null;
}

export interface TieOutSummary {
  schema_version?: string;
  controls: ControlResult[];
  compared: number;
  with_exceptions: number;
  not_evaluated: number;
  coverage_account_count: number;
  scope_note: string;
  legacy?: boolean;
  // Slice 1 payload still parsed for tests that inspect old fixtures.
  groups?: TieOutGroup[];
  with_gap?: number;
  not_compared?: number;
}

export interface TieOutGroup {
  key: TieOutGroupKey;
  label: string;
  status: "clean" | "gap";
  files: string[];
}

export const TIE_OUT_GROUP_ORDER: TieOutGroupKey[] = [
  "payroll",
  "supplier_invoices",
  "contracts",
  "other",
];

export const TIE_OUT_GROUP_LABELS: Record<TieOutGroupKey, string> = {
  payroll: "Payroll",
  supplier_invoices: "Vendors",
  contracts: "Contracts",
  other: "Other supporting files",
};

export const CONTROL_STATUS_LABEL: Record<ControlStatus, string> = {
  tied_out: "Tied out",
  has_exceptions: "Has exceptions",
  mapping_required: "Mapping required",
  source_missing: "Source missing",
  not_compared: "Not compared",
};

const PATTERNS: { type: string; needles: string[] }[] = [
  { type: "general_ledger", needles: ["gl", "general_ledger", "quickbooks", "qb", "gl_export", "ledger"] },
  { type: "payroll", needles: ["payroll", "salary", "salaries", "wages", "gusto", "adp", "rippling"] },
  { type: "contracts", needles: ["contract", "subscription", "recurring", "roster", "customer"] },
  { type: "supplier_invoices", needles: ["invoice", "supplier", "vendor", "purchase", "bill", "ap"] },
  { type: "bank_statement", needles: ["bank", "bank_statement", "checking", "deposit_account"] },
  { type: "processor_settlement", needles: ["stripe", "shopify_payout", "paypal", "square", "processor", "settlement", "payout"] },
];

function stem(filename: string): string {
  const base = filename.split(/[/\\]/).pop() ?? filename;
  return base.toLowerCase().replace(/-/g, "_").replace(/ /g, "_").split(".")[0] ?? "";
}

function matchFileType(filename: string): string | null {
  const s = stem(filename);
  for (const { type, needles } of PATTERNS) {
    if (needles.some((n) => s.includes(n))) return type;
  }
  return null;
}

export function tieOutGroupForFilename(filename: string): TieOutGroupKey | null {
  const kind = matchFileType(filename);
  if (kind === "general_ledger") return null;
  if (kind === "payroll" || kind === "supplier_invoices" || kind === "contracts") {
    return kind;
  }
  return "other";
}

export function tieOutGroupFromSources(
  sources: { source_file?: string | null }[] | undefined,
  cardKind?: string | null,
  isGlOnly?: boolean
): TieOutGroupKey | null {
  if (cardKind === "coverage" || isGlOnly) return null;
  for (const src of sources ?? []) {
    if (!src.source_file) continue;
    const group = tieOutGroupForFilename(src.source_file);
    if (group) return group;
  }
  return "other";
}
