"""Deterministic check: the narrative must not contradict the control cards.

No LLM, no I/O, no arithmetic. A coverage account (card_kind "coverage" or the
is_gl_only hint) is a GL account with no supporting file. The cards say "not
compared" and "this is not a missing journal entry". A narrative sentence that
names such an account and calls it a missing journal entry (or high/medium
severity) contradicts them and is rejected. Source-only items (a real
missing_je) and the stale_reference gap are not coverage items and pass.

A sentence that names no account ("Some journal entries may be missing.") is
judged against the cards as a whole: when no card is classified missing_je,
any non-negated missing-journal-entry wording is rejected.
"""

from __future__ import annotations

import re

from backend.tools.tie_out_summary import is_coverage_item

# "not a missing journal entry" is the cards' own wording and is allowed.
_NEGATED = re.compile(
    r"\b(?:not|isn['’]t|is not|never|no)\s+(?:a\s+|an\s+)?"
    r"missing[\s_-]*(?:journal[\s_-]*entr(?:y|ies)|je)\b",
    re.IGNORECASE,
)
_MISSING_JE = re.compile(
    r"missing[\s_-]*(?:journal[\s_-]*entr(?:y|ies)|je)\b"
    r"|journal[\s_-]*entr(?:y|ies)\s+(?:may\s+be|is|are)\s+missing"
    r"|unrecorded\s+(?:journal|entr)",
    re.IGNORECASE,
)
_SEVERITY = re.compile(r"\b(?:high|medium)[\s-]*severity\b", re.IGNORECASE)


def coverage_accounts(reconciliations: list[dict] | None) -> set[str]:
    """Account names whose card is coverage (no supporting file)."""
    names: set[str] = set()
    for item in reconciliations or []:
        if isinstance(item, dict) and is_coverage_item(item):
            name = str(item.get("account") or "").strip()
            if name:
                names.add(name)
    return names


def known_accounts(
    reconciliations: list[dict] | None, summary_accounts: object = None
) -> set[str]:
    """Every account name the narrative may mention (cards + P&L summary)."""
    names: set[str] = set()
    for item in reconciliations or []:
        if isinstance(item, dict) and str(item.get("account") or "").strip():
            names.add(str(item["account"]).strip())
    if isinstance(summary_accounts, dict):
        names.update(str(k).strip() for k in summary_accounts if str(k).strip())
    return names


def _named(sentence: str, accounts: set[str]) -> set[str]:
    """Accounts named in a sentence. Longest name first, and a match is blanked
    out so "Insurance" is not found inside "Auto Insurance Premium"."""
    found: set[str] = set()
    text = sentence
    for name in sorted(accounts, key=len, reverse=True):
        pattern = r"(?<![\w&])" + re.escape(name) + r"(?![\w&])"
        if re.search(pattern, text, re.IGNORECASE):
            found.add(name)
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return found


def find_coverage_contradictions(
    narrative: str,
    covered: set[str],
    known: set[str] | None = None,
) -> list[str]:
    """Sentences that call a coverage account a missing JE or high/medium severity.

    A sentence that names no account ("Classification: missing_je.") belongs to
    the account named most recently in the same paragraph. A sentence is flagged
    only when every account it is about is a coverage account, so a real
    source-only missing_je or the stale_reference gap is never flagged.
    Empty list means the narrative agrees with the cards.
    """
    if not narrative or not covered:
        return []
    accounts = set(known or set()) | set(covered)
    found: list[str] = []
    for paragraph in narrative.split("\n"):
        about: set[str] = set()
        for raw in re.split(r"(?<=[.!?])\s+", paragraph):
            text = raw.strip()
            if not text:
                continue
            named = _named(text, accounts)
            if named:
                about = named
            if not about or not about <= covered:
                continue
            scrubbed = _NEGATED.sub("", text)
            if _MISSING_JE.search(scrubbed) or _SEVERITY.search(scrubbed):
                found.append(text)
    return found


def has_missing_je_card(reconciliations: list[dict] | None) -> bool:
    """True when at least one non-coverage card is classified missing_je."""
    return any(
        isinstance(item, dict)
        and not is_coverage_item(item)
        and item.get("classification") == "missing_je"
        for item in reconciliations or []
    )


def find_unbacked_missing_je(narrative: str, backed: bool) -> list[str]:
    """Sentences that claim a missing journal entry when no card says missing_je.

    `backed` comes from the final card classes (`has_missing_je_card`), never
    from the narrative. Negated wording ("not a missing journal entry") passes.
    """
    if not narrative or backed:
        return []
    found: list[str] = []
    for paragraph in narrative.split("\n"):
        for raw in re.split(r"(?<=[.!?])\s+", paragraph):
            text = raw.strip()
            if text and _MISSING_JE.search(_NEGATED.sub("", text)):
                found.append(text)
    return found
