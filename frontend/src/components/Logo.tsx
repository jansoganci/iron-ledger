interface LogoMarkProps {
  /** Pixel size of the square mark. */
  size?: number;
  className?: string;
}

/** TrueCost mark: a ledger rule above a check — "verified numbers". */
export function LogoMark({ size = 28, className }: LogoMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <rect width="64" height="64" rx="14" fill="#252421" />
      <rect x="14" y="15" width="36" height="6" rx="3" fill="#F08408" />
      <path
        d="M19 38 L28 47 L46 29"
        fill="none"
        stroke="#FAFAF8"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
