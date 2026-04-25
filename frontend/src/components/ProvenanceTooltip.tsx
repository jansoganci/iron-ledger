import * as Tooltip from "@radix-ui/react-tooltip";

interface ProvenanceTooltipProps {
  children: React.ReactNode;
  sourceFile: string | null | undefined;
  sourceColumn?: string | null;
}

/**
 * Wraps any content with a hover tooltip showing "From [file] — column '[col]'".
 * When provenance is unavailable, renders children unwrapped.
 */
export function ProvenanceTooltip({
  children,
  sourceFile,
  sourceColumn,
}: ProvenanceTooltipProps) {
  const tip = [
    sourceFile,
    sourceColumn ? `column '${sourceColumn}'` : null,
  ]
    .filter(Boolean)
    .join(" — ");

  if (!tip) {
    return <span data-numeric>{children}</span>;
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span
            data-numeric
            role="button"
            tabIndex={0}
            className="cursor-help underline decoration-dotted decoration-text-secondary underline-offset-2 rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            {children}
          </span>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="rounded bg-text-primary px-2 py-1 text-xs text-white shadow-md z-50"
            sideOffset={4}
          >
            {tip}
            <Tooltip.Arrow className="fill-text-primary" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
