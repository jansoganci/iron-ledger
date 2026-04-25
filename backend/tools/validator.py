from __future__ import annotations

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema

from backend.logger import get_logger

logger = get_logger(__name__)

# Golden Schema for a normalized P&L entry DataFrame.
# Runs on the OUTPUT of tools.normalizer.apply_plan — not on raw files.
# strict=True catches any stray column the Normalizer forgot to drop.
#
# Known transitional breakage: existing agents/parser.py still injects
# a "period" column and calls validate() pre-Normalizer. That path will
# reject until Phase 3 rewires Parser to go through apply_plan().
_SCHEMA = DataFrameSchema(
    {
        "account": Column(str, nullable=False),
        "account_code": Column(str, nullable=True),
        "amount": Column(float, nullable=False),
        "date": Column(pa.DateTime, nullable=False),
        "parent_category": Column(str, nullable=True),
        "department": Column(str, nullable=True),
        "description": Column(str, nullable=True),
    },
    strict=True,
    coerce=True,
)


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Validate *df* against the P&L pandera schema.

    Returns the coerced DataFrame on success.
    Raises pa.errors.SchemaError with a plain-English message on failure.
    """
    try:
        return _SCHEMA.validate(df)
    except pa.errors.SchemaError as exc:
        # Re-raise with a plain-English message; caller surfaces via messages.PARSE_FAILED.
        col = getattr(exc, "schema_context", None) or "unknown column"
        raise pa.errors.SchemaError(
            _SCHEMA,
            df,
            f"We couldn't read the '{col}' column. Please check for invalid values.",
        ) from exc
