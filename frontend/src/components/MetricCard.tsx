import React from "react";

interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  subtext?: React.ReactNode;
  icon?: React.ReactNode;
}

/**
 * Single numeric tile used by the Dashboard. Per docs/design.md §4 / §Design Language:
 * neutral surface, tabular numerals on the value, subdued secondary-text subtext.
 * Not color-coded — decoration is the severity chips' job, not metric tiles.
 */
export function MetricCard({ label, value, subtext, icon }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        {icon && (
          <span className="text-text-secondary shrink-0" aria-hidden>
            {icon}
          </span>
        )}
        <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">
          {label}
        </span>
      </div>
      <div
        className="font-hero-num text-2xl font-semibold text-text-primary"
        data-numeric
      >
        {value}
      </div>
      {subtext && (
        <div className="mt-1 text-sm text-text-secondary">{subtext}</div>
      )}
    </div>
  );
}
