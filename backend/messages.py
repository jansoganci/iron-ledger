"""Single source of truth for every user-facing string.

Exceptions never hold copy. This module is the only place strings live.
"""

UNAUTHORIZED = "Your session has expired. Please sign in again."
FORBIDDEN = "You don't have access to this resource."

UNSUPPORTED_FORMAT = (
    "'{filename}' is not a supported format. "
    "Upload an Excel (.xlsx, .xls, .xlsm) or CSV file."
)
PARSE_FAILED = (
    "We couldn't read this file. "
    "Please check that it contains financial data and try again."
)
MAPPING_FAILED = (
    "We couldn't map these columns to US GAAP categories: {columns}. "
    "Please review and confirm the mapping."
)
FILE_HAS_NO_VALID_COLUMNS = (
    "This file looks empty or contains only columns we had to remove for privacy reasons. "
    "Please upload a file with financial data."
)

GUARDRAIL_FAILED = (
    "We couldn't verify the report numbers after two attempts. "
    "Download the raw data below and try again."
)
NOT_FOUND = "No verified report found for this company and period."

MAIL_FAILED = (
    "The email couldn't be sent. " "Your report is still available in the dashboard."
)

RATE_LIMITED = (
    "You've made too many requests. "
    "Please wait {retry_after_seconds} seconds before trying again."
)

UPLOAD_FAILED = (
    "We couldn't save your file after several attempts. " "Please try uploading again."
)

INVALID_PERIOD = (
    "'{period}' is not a valid period. "
    "Use the first day of the month, e.g. 2026-03-01."
)

DUPLICATE_ENTRY = (
    "A file for this period already exists. "
    "Uploading again will replace the previous data."
)

INTERNAL_ERROR = (
    "Something went wrong on our end. " "Please try again — your data is safe."
)

DISCOVERING_STEP_LABEL = "Understanding your file..."

DISCOVERY_LOW_CONFIDENCE = (
    "We need you to review how we read this file before continuing."
)

MAPPING_FAILED = "We couldn't classify your accounts. Please re-upload."
MAPPING_INVALID_GL_ACCOUNT = "One or more selected GL accounts is no longer valid."

DISCOVERY_REJECTED = (
    "You rejected our reading of this file. Please try a different export."
)

COMPANY_CREATE_FAILED = "We couldn't create your workspace. Please try again."
