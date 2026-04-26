"""AccountMapper — translate raw source values to canonical GL account names.

Called from the orchestrator BEFORE parse_file_silently's final aggregation.
Operates on unique account values only; the caller applies the result via
pandas .map() inside parse_file_silently.

No database calls. No cache reads or writes (post-MVP). Only a single Haiku
call per non-GL file plus validation of the output against the GL pool.
"""

from __future__ import annotations

from backend.domain.contracts import (
    AccountMappingResponse,
    DEFAULT_GL_CATEGORIES,
    MappingDraft,
    MappingDraftItem,
    SourceFileType,
)
from backend.domain.ports import LLMClient
from backend.logger import get_logger

logger = get_logger(__name__)

MAPPING_MODEL = "claude-haiku-4-5-20251001"


class AccountMapper:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def build_draft(
        self,
        unique_values: list[str],
        file_type: SourceFileType,
        source_file: str,
        gl_pool: list[str],
    ) -> tuple[dict[str, str | None], MappingDraft]:
        """Call Haiku, validate output, return (mapping_dict, draft).

        Args:
            unique_values: deduplicated account values extracted from the file.
            file_type: detected file type — used as prompt context for Haiku.
            source_file: original filename, stored in draft items for UI provenance.
            gl_pool: valid GL account names. Haiku output is validated against this.
                     Falls back to DEFAULT_GL_CATEGORIES when empty.

        Returns:
            mapping_dict: {raw_value: gl_account_name_or_None}
            draft: MappingDraft for the user review UI
        """
        effective_pool = gl_pool if gl_pool else list(DEFAULT_GL_CATEGORIES)

        if not unique_values:
            return {}, MappingDraft(items=[], gl_account_pool=effective_pool)

        ctx = {
            "values": unique_values,
            "file_type": file_type,
            "gl_accounts": effective_pool,
        }

        resp: AccountMappingResponse = self._llm.call(
            "account_mapping_prompt.txt",
            MAPPING_MODEL,
            ctx,
            AccountMappingResponse,
        )

        mapping_dict: dict[str, str | None] = {}
        draft_items: list[MappingDraftItem] = []

        for value in unique_values:
            decision = resp.mappings.get(value)

            if decision is None:
                # Haiku did not return an entry for this value
                gl = None
                confident = False
            else:
                gl = decision.gl_account
                confident = decision.confident
                # Hallucination guard: reject any name not in the supplied pool
                if gl is not None and gl not in effective_pool:
                    logger.warning(
                        "account_mapper_hallucination",
                        extra={
                            "value": value,
                            "rejected_gl": gl,
                            "file": source_file,
                        },
                    )
                    gl = None
                    confident = False

            mapping_dict[value] = gl
            draft_items.append(
                MappingDraftItem(
                    source_pattern=value,
                    source_file=source_file,
                    file_type=file_type,
                    suggested_gl_account=gl,
                    confident=confident,
                )
            )

        logger.info(
            "account_mapping_complete",
            extra={
                "file": source_file,
                "file_type": file_type,
                "total": len(unique_values),
                "confident": sum(1 for i in draft_items if i.confident),
                "unsure": sum(1 for i in draft_items if not i.confident),
            },
        )

        draft = MappingDraft(items=draft_items, gl_account_pool=effective_pool)
        return mapping_dict, draft
