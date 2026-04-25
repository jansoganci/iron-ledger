// Mirror of backend/messages.py for strings the frontend references directly,
// PLUS client-side-only strings (file validation, network fallback) that never
// originate from the backend. Keep these in sync with backend/messages.py —
// reconciliation check on Day 5.

export const CLIENT_MESSAGES = {
  // Client-side file validation (rejected before upload hits the backend)
  UNSUPPORTED_FORMAT: (filename: string) =>
    `\`${filename}\` is not a supported format — upload an Excel or CSV file.`,
  FILE_TOO_LARGE: (filename: string) =>
    `\`${filename}\` is larger than 10 MB — please split the file.`,

  // Auth — never reveal which field was wrong (avoid account enumeration)
  AUTH_FAILED: "Email or password is incorrect. Please try again.",
  SESSION_EXPIRED: "Your session has expired. Please sign in again.",
  EMAIL_ALREADY_REGISTERED:
    "An account with this email already exists. Sign in instead.",
  PASSWORD_TOO_SHORT: "Password must be at least 8 characters.",
  PASSWORDS_DONT_MATCH: "Passwords don't match.",
  SIGNUP_FAILED: "We couldn't create your account. Please try again.",

  // Network / fetch fallbacks
  NETWORK_ERROR: "We couldn't reach the server. Check your connection and try again.",

  // Error boundary fallback
  UNKNOWN_ERROR: "Something went wrong. Please refresh — your data is safe.",

  // Mirrors of backend keys (kept in sync with backend/messages.py)
  RATE_LIMITED: "You're going too fast. Please wait a moment and try again.",
  FORBIDDEN: "You don't have access to this resource.",

  // Onboarding
  ONBOARDING_COMPANY_FAILED: "We couldn't set up your workspace. Please try again.",
} as const;
