import { cn } from "../lib/utils";
import { recentPeriods } from "../lib/formatters";

interface PeriodSelectorProps {
  value: string;
  onChange: (period: string) => void;
  label?: string;
  disabled?: boolean;
  monthsBack?: number;
}

export function PeriodSelector({
  value,
  onChange,
  label = "Which period?",
  disabled = false,
  monthsBack = 24,
}: PeriodSelectorProps) {
  const options = recentPeriods(monthsBack);

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-text-primary">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          "w-full rounded-md border border-border bg-surface px-3 py-2",
          "text-sm text-text-primary",
          "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1",
          disabled && "opacity-60 cursor-not-allowed"
        )}
      >
        {!options.find((o) => o.value === value) && (
          <option value={value}>{value}</option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
