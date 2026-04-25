import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock,
  RefreshCw,
  Shuffle,
} from "lucide-react";
import { cn } from "../lib/utils";

export type Classification =
  | "timing_cutoff"
  | "categorical_misclassification"
  | "missing_je"
  | "stale_reference"
  | "accrual_mismatch"
  | "structural_explained";

interface BadgeConfig {
  label: string;
  icon: React.ElementType;
  classes: string;
}

const CONFIG: Record<Classification, BadgeConfig> = {
  timing_cutoff: {
    label: "Timing cutoff",
    icon: Clock,
    classes: "bg-severity-medium-bg text-severity-medium-fg",
  },
  categorical_misclassification: {
    label: "Wrong category",
    icon: Shuffle,
    classes: "bg-severity-high-bg text-severity-high-fg",
  },
  missing_je: {
    label: "Missing JE",
    icon: AlertTriangle,
    classes: "bg-severity-high-bg text-severity-high-fg",
  },
  stale_reference: {
    label: "Stale reference",
    icon: RefreshCw,
    classes: "bg-orange-100 text-orange-700",
  },
  accrual_mismatch: {
    label: "Accrual mismatch",
    icon: Calendar,
    classes: "bg-orange-100 text-orange-700",
  },
  structural_explained: {
    label: "Explained",
    icon: CheckCircle,
    classes: "bg-severity-normal-bg text-severity-normal-fg",
  },
};

interface ClassificationBadgeProps {
  classification: Classification;
  className?: string;
}

export function ClassificationBadge({
  classification,
  className,
}: ClassificationBadgeProps) {
  const config = CONFIG[classification];
  if (!config) return null;
  const { label, icon: Icon, classes } = config;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        classes,
        className
      )}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      {label}
    </span>
  );
}
