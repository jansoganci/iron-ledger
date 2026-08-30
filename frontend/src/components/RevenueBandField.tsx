export const REVENUE_BANDS = [
  { value: "under_100k", label: "Under $100k / month" },
  { value: "100k_250k", label: "$100k–$250k / month" },
  { value: "250k_500k", label: "$250k–$500k / month" },
  { value: "500k_plus", label: "$500k+ / month" },
] as const;

export type RevenueBand = (typeof REVENUE_BANDS)[number]["value"];

export function bandLabel(value: string | null | undefined): string {
  if (!value) return "Not set";
  return REVENUE_BANDS.find((b) => b.value === value)?.label ?? "Not set";
}

interface Props {
  value: RevenueBand | "" | null;
  onChange: (value: RevenueBand) => void;
  disabled?: boolean;
  name?: string;
}

export function RevenueBandField({
  value,
  onChange,
  disabled = false,
  name = "monthly_revenue_band",
}: Props) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="block text-sm font-medium text-text-primary mb-1.5">
        Typical monthly revenue
      </legend>
      <p className="text-xs text-text-secondary mb-2.5">
        Not annual. Not a target. What usually lands in a month.
      </p>
      <div className="space-y-2">
        {REVENUE_BANDS.map((band) => (
          <label
            key={band.value}
            className="flex items-center gap-2.5 text-sm text-text-primary cursor-pointer"
          >
            <input
              type="radio"
              name={name}
              value={band.value}
              checked={value === band.value}
              onChange={() => onChange(band.value)}
              className="h-4 w-4 accent-accent focus:ring-2 focus:ring-accent"
            />
            <span>{band.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
