from __future__ import annotations

import json

from pydantic import ValidationError

from backend.domain.contracts import DiscoveryPlan
from backend.domain.errors import DiscoveryFailed, DiscoveryLowConfidence
from backend.domain.ports import LLMClient
from backend.logger import get_logger, get_trace_id

logger = get_logger(__name__)

DISCOVERY_MODEL = "claude-haiku-4-5-20251001"
DISCOVERY_PROMPT = "discovery_prompt.txt"
CONFIDENCE_THRESHOLD = 0.80


class _SemanticValidationError(Exception):
    """Plan parsed, but violates domain rules (e.g. header_row_index out of range)."""


class DiscoveryAgent:
    """Structure-discovery agent. Claude identifies shape; Python decides retry.

    Stateless by design: does not transition run state or persist the plan.
    The caller (Phase 3 parser rewire) owns those responsibilities so this
    agent can ship before the DISCOVERING state and runs.discovery_plan
    column exist.

    Raises:
        DiscoveryLowConfidence(plan): plan valid but confidence < 0.80.
            Carries the plan so the caller can persist it and transition
            the run to AWAITING_CONFIRMATION.
        DiscoveryFailed: both the initial call and the one retry produced
            invalid output. Caller should transition to DISCOVERY_FAILED.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def discover(self, run_id: str, sample: list[dict]) -> DiscoveryPlan:
        sample_size = len(sample)
        context: dict = {"rows": sample}

        plan, error = self._call_and_validate(context, sample_size)
        if plan is None:
            logger.info(
                "discovery retry",
                extra={
                    "event": "discovery_retry",
                    "trace_id": get_trace_id(),
                    "run_id": run_id,
                    "previous_error": error,
                },
            )
            retry_context = {"rows": sample, "previous_error": error}
            plan, error = self._call_and_validate(retry_context, sample_size)
            if plan is None:
                logger.error(
                    "discovery failed after retry",
                    extra={
                        "event": "discovery_failed",
                        "trace_id": get_trace_id(),
                        "run_id": run_id,
                        "final_error": error,
                    },
                )
                raise DiscoveryFailed(f"Discovery failed after retry: {error}")

        logger.info(
            "discovery complete",
            extra={
                "event": "discovery_complete",
                "trace_id": get_trace_id(),
                "run_id": run_id,
                "header_row_index": plan.header_row_index,
                "skip_rows_count": len(plan.skip_row_indices),
                "mapped_columns_count": len(plan.column_mapping),
                "hierarchy_hints_count": len(plan.hierarchy_hints),
                "discovery_confidence": plan.discovery_confidence,
            },
        )

        if plan.discovery_confidence < CONFIDENCE_THRESHOLD:
            raise DiscoveryLowConfidence(plan)

        return plan

    def _call_and_validate(
        self,
        context: dict,
        sample_size: int,
    ) -> tuple[DiscoveryPlan | None, str]:
        try:
            plan = self._llm.call(
                prompt=DISCOVERY_PROMPT,
                model=DISCOVERY_MODEL,
                context=context,
                schema=DiscoveryPlan,
            )
        except (ValidationError, json.JSONDecodeError) as exc:
            return None, f"schema violation: {exc}"

        if not isinstance(plan, DiscoveryPlan):
            return None, "adapter returned non-DiscoveryPlan object"

        try:
            self._semantic_validate(plan, sample_size)
        except _SemanticValidationError as exc:
            return None, str(exc)

        return plan, ""

    @staticmethod
    def _semantic_validate(plan: DiscoveryPlan, sample_size: int) -> None:
        if plan.header_row_index >= sample_size:
            raise _SemanticValidationError(
                f"header_row_index {plan.header_row_index} "
                f">= sample size {sample_size}"
            )
        mapped_fields = set(plan.column_mapping.values())
        if "amount" not in mapped_fields:
            raise _SemanticValidationError(
                "no column mapped to 'amount' — at least one is required"
            )
        if "account" not in mapped_fields:
            raise _SemanticValidationError(
                "no column mapped to 'account' — at least one is required"
            )
