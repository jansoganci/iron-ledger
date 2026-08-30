"""Item 1 — bank/processor three-way matcher.

Deterministic pandas only. No Claude, no DB, no I/O, no fuzzy matching, no
"close enough" amounts. Every number here is computed in Python and lands on
``BatchMatch``; Claude only ever copies those values.

Spec: docs/sprint/kova2-implementation-plan.md, item 1, sections C.5 / C.5.1,
including decisions E.1 (fee_pct computed, never stored), E.2 (N1-N3 amount
rules), E.3 (S1-S4 settlement_date precedence), E.4 (match_id construction),
E.5 (why the zero tolerance is what makes the fallback safe) and E.7 (the
seven-row classification priority, ambiguous first).

MVP boundary (locked): one processor, one Undeposited Funds account, one bank,
one period. No A2X, no auto-JE, no multi-currency, no many-to-many splits.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import pandas as pd

from backend.domain.contracts import BatchMatch

MatchKind = Literal["id", "amount_date", "none"]
LeftoverSide = Literal["fsm", "bank"]

# The 3-8% processor fee band. Reused from Kova 1's account-total hint
# (hint_computer._FEE_BAND_MIN/_MAX) — do not retune here.
_FEE_BAND_MIN = 0.03
_FEE_BAND_MAX = 0.08


# ---------------------------------------------------------------------------
# Identity helpers (shipped inert in PR-A)
# ---------------------------------------------------------------------------


def norm(value: object | None) -> str | None:
    """Normalize a join id: ``None`` when null/blank, else stripped + casefolded.

    Per C.5.1: ``norm(id) := None if id is null/blank else
    str(id).strip().casefold()``. A blank ref is not an id — it must never
    match another blank ref on ID.
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text.casefold()


def fee_pct(gross: float, fee: float) -> float | None:
    """Internal pandas gate for the 3-8% band (decision E.1).

    Never stored on ``BatchMatch``, never serialized, never a prompt
    placeholder. Returns None when gross is 0.
    """
    if gross == 0:
        return None
    return abs(fee) / abs(gross)


def build_match_id(
    match_kind: MatchKind,
    *,
    id_val: object | None = None,
    amount: float | None = None,
    day: date | None = None,
    side: LeftoverSide | None = None,
    ref: object | None = None,
    seq: int | None = None,
) -> str:
    """Construct the deterministic ``BatchMatch.match_id`` (decision E.4).

    Same input files must always produce the same id, because C.8 may key
    per-batch speech off it. Every component is derived from file content:
    the normalized id, the amount rounded to 2dp, the calendar date, and for
    null-ref leftovers a ``seq`` taken from ``_orig_row_index`` order.

    **Forbidden by spec** — do not "helpfully" substitute any of these:
    a UUID, a hash of object identity, a global insertion counter, or anything
    derived from dict/set iteration order. ``tests/tools/test_batch_matcher_scaffold.py``
    is written to fail if one is introduced.

    Ambiguity is a document defect, not a coding decision: this function raises
    rather than inventing a fallback when a required component is missing.
    """
    if match_kind == "id":
        normalized = norm(id_val)
        if normalized is None:
            raise ValueError(
                "match_kind='id' requires a non-blank id_val; a blank ref "
                "never forms an ID match (C.5.1 join-key hierarchy)"
            )
        return normalized

    if match_kind == "amount_date":
        if amount is None or day is None:
            raise ValueError(
                "match_kind='amount_date' requires the group key (amount, day); "
                "it is taken from the group, never from a member row"
            )
        return f"ad:{amount:.2f}:{day.isoformat()}"

    if match_kind == "none":
        if side not in ("fsm", "bank"):
            raise ValueError("match_kind='none' requires side='fsm' or side='bank'")
        normalized_ref = norm(ref)
        if normalized_ref is not None:
            return f"none:{side}:{normalized_ref}"
        if amount is None or day is None or seq is None:
            raise ValueError(
                "a null-ref leftover requires amount, day and seq; seq is the "
                "0-based ordinal among same-side leftovers sharing that amount "
                "and date, in ascending _orig_row_index order"
            )
        return f"none:{side}:{amount:.2f}:{day.isoformat()}:{seq}"

    raise ValueError(f"unknown match_kind: {match_kind!r}")


# ---------------------------------------------------------------------------
# Row normalization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    """One normalized sidecar row, from any of the three frames."""

    side: Literal["fsm", "gl", "bank"]
    index: int  # _orig_row_index — file order, drives seq determinism
    ref_raw: str | None
    ref_norm: str | None
    day: date | None
    gross: float | None = None
    net: float | None = None
    amount: float | None = None
    gl_account: str | None = None

    @property
    def key_amount(self) -> float | None:
        """The Pass-2 grouping amount for this row.

        Per the pseudocode: fsm.net if present else fsm.gross; gl.amount;
        bank.net if present else bank.amount. Note (decision E.5) that when
        the FSM frame has no `net` column this puts an FSM **gross** into the
        same key space as a bank **net** — which is safe only because the
        grouping demands exact equality after rounding, so the two can meet
        only when the fee is genuinely zero.
        """
        if self.side == "fsm":
            value = self.net if self.net is not None else self.gross
        elif self.side == "gl":
            value = self.amount
        else:
            value = self.net if self.net is not None else self.amount
        return None if value is None else round(float(value), 2)


def _cell(row: pd.Series, column: str) -> object | None:
    if column not in row.index:
        return None
    value = row[column]
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    return value


def _as_float(value: object | None) -> float | None:
    return None if value is None else round(float(value), 2)


def _as_date(value: object | None) -> date | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _read_rows(
    frame: pd.DataFrame | None,
    side: Literal["fsm", "gl", "bank"],
    *,
    id_col: str,
    date_col: str,
) -> list[_Row]:
    """Normalize one sidecar frame into `_Row`s, in ascending file order."""
    if frame is None or frame.empty:
        return []
    rows: list[_Row] = []
    for position, (_, raw) in enumerate(frame.iterrows()):
        ref = _cell(raw, id_col)
        rows.append(
            _Row(
                side=side,
                index=int(_cell(raw, "_orig_row_index") or position),
                ref_raw=None if ref is None else str(ref),
                ref_norm=norm(ref),
                day=_as_date(_cell(raw, date_col)),
                gross=_as_float(_cell(raw, "gross")),
                net=_as_float(_cell(raw, "net")),
                amount=_as_float(_cell(raw, "amount")),
                gl_account=(
                    None
                    if _cell(raw, "gl_account") is None
                    else str(_cell(raw, "gl_account"))
                ),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Amount rules N1-N3 (decision E.2) and settlement date rules S1-S4 (E.3)
# ---------------------------------------------------------------------------


def _amounts(
    fsm: _Row | None,
    bank: _Row | None,
    *,
    ambiguous: bool = False,
    group_amount: float | None = None,
) -> tuple[float, float, float]:
    """Return ``(gross, net, fee)`` per N1 -> N2 -> N3.

    Ambiguous matches never borrow a member row's amount — that would be the
    silent pick rule (c) forbids. A Pass-2 ambiguous group uses its amount key;
    a Pass-1 ambiguous group has no key and reports zeros.
    """
    if ambiguous:
        value = 0.0 if group_amount is None else round(float(group_amount), 2)
        return value, value, 0.0

    has_bank = bank is not None
    has_fsm = fsm is not None

    if has_bank:
        # N1.1 / N1.2 — bank `net`, else bank `amount` (a bank amount IS net).
        net = bank.net if bank.net is not None else bank.amount
        if net is None:
            net = bank.gross
        # N2.1 — bank gross; N2.2 — else FSM gross; N2.3 — else net.
        if bank.gross is not None:
            gross = bank.gross
        elif has_fsm and fsm.gross is not None:
            gross = fsm.gross
        else:
            gross = net
    elif has_fsm:
        # N2.2 then N1.3 — no settlement row means no observed deduction.
        gross = fsm.gross if fsm.gross is not None else 0.0
        net = gross
    else:
        # Terminal case: neither settlement nor FSM row. Only reachable for an
        # ambiguous GL-only group, which `_classify` returns at rule 1 before
        # any amount is read.
        gross = net = 0.0

    gross = round(float(gross or 0.0), 2)
    net = round(float(net or 0.0), 2)
    return gross, net, round(gross - net, 2)


def _settlement_date(
    bank: _Row | None,
    *,
    ambiguous: bool = False,
    match_kind: MatchKind = "id",
    group_day: date | None = None,
) -> date | None:
    """Return ``settlement_date`` per S1-S4.

    S1: sourced ONLY from the bank/settlement row. FSM `collected_date` and GL
    `gl_date` are never used, at any precedence.
    S2: None when the match has no bank row — which makes such a match
    permanently ineligible for `timing_cutoff` (intentional; see E.3).
    S4: an ambiguous Pass-2 group takes its date key; an ambiguous Pass-1 group
    gets None.
    """
    if ambiguous:
        return group_day if match_kind == "amount_date" else None
    return None if bank is None else bank.day


# ---------------------------------------------------------------------------
# Classification — the seven-row priority order (decision E.7)
# ---------------------------------------------------------------------------


def _classify(
    m: BatchMatch, period_end: date, uf_account_name: str
) -> BatchMatch | None:
    """Apply the classification priority. First matching rule wins.

    Returns None for the true negative (rule 6) — a clean, fully-tied batch
    produces no card at all.
    """
    has_gl = m.gl_account is not None or m.gl_ref is not None or m.gl_amount is not None
    pct = fee_pct(m.gross, m.fee)  # E.1: computed here, never a model field

    # 1. Ambiguous outranks everything, including cutoff: we cannot assert that
    #    a *specific* batch settled late when we refused to identify which row
    #    it is.
    if m.ambiguous:
        m.classification = "stale_reference"
        m.unmatched = True
        return m

    # 2. Cutoff beats fee AND beats missing-GL.
    if m.settlement_date is not None and m.settlement_date > period_end:
        m.classification = "timing_cutoff"
        return m

    # 3. No GL row. Sits above the fee band so PZ-300 (fee_pct 0.04, no GL) is
    #    a missing JE, not a fee story.
    if not has_gl:
        m.classification = "missing_je"
        m.unmatched = True
        return m

    # 4. Wrong clearing account. Above rule 6, which is why PZ-500 (fee 0.00,
    #    gl_amount == net) surfaces instead of being silently dropped.
    if m.gl_account != uf_account_name:
        m.classification = "categorical_misclassification"
        return m

    # 5. Fee band — only reachable with a GL row on the UF account.
    if pct is not None and _FEE_BAND_MIN <= pct <= _FEE_BAND_MAX:
        m.classification = "structural_explained"
        return m

    # 6. True negative: clean three-way tie-out. Drop, no card.
    if (
        m.fee == 0
        and m.gl_amount is not None
        and round(m.gl_amount, 2) == round(m.net, 2)
    ):
        return None

    # 7. Matched residue outside the fee band.
    m.classification = "stale_reference"
    return m


# ---------------------------------------------------------------------------
# Match construction
# ---------------------------------------------------------------------------


def _emit(
    *,
    match_id: str,
    match_kind: MatchKind,
    fsm: _Row | None,
    gl: _Row | None,
    bank: _Row | None,
) -> BatchMatch:
    gross, net, fee = _amounts(fsm, bank)
    return BatchMatch(
        match_id=match_id,
        processor_ref=None if fsm is None else fsm.ref_raw,
        bank_ref=None if bank is None else bank.ref_raw,
        gl_ref=None if gl is None else gl.ref_raw,
        gl_account=None if gl is None else gl.gl_account,
        gl_amount=None if gl is None else gl.amount,
        gross=gross,
        net=net,
        fee=fee,
        settlement_date=_settlement_date(bank),
        match_kind=match_kind,
        ambiguous=False,
        candidate_count=1,
        unmatched=False,
    )


def _emit_ambiguous(
    *,
    match_id: str,
    match_kind: MatchKind,
    candidate_count: int,
    group_amount: float | None = None,
    group_day: date | None = None,
) -> BatchMatch:
    gross, net, fee = _amounts(None, None, ambiguous=True, group_amount=group_amount)
    return BatchMatch(
        match_id=match_id,
        processor_ref=None,
        bank_ref=None,
        gl_ref=None,
        gl_account=None,
        gl_amount=None,
        gross=gross,
        net=net,
        fee=fee,
        settlement_date=_settlement_date(
            None, ambiguous=True, match_kind=match_kind, group_day=group_day
        ),
        match_kind=match_kind,
        ambiguous=True,
        candidate_count=candidate_count,
        unmatched=True,
    )


@dataclass
class MatchResult:
    """Matcher output: classified cards plus the two unmatched counters."""

    matches: list[BatchMatch] = field(default_factory=list)
    unmatched_processor_count: int = 0
    unmatched_bank_count: int = 0


def last_day_of(period: date) -> date:
    return date(
        period.year, period.month, calendar.monthrange(period.year, period.month)[1]
    )


def match(
    fsm_df: pd.DataFrame | None,
    gl_df: pd.DataFrame | None,
    bank_df: pd.DataFrame | None,
    period: date,
    uf_account_name: str,
) -> MatchResult:
    """Run the three passes and classify. Deterministic for identical input.

    Ordering note: ids and groups are iterated in sorted order so the output
    list is stable across runs. Nothing here depends on dict/set iteration
    order (decision E.4's ban list).
    """
    period_end = last_day_of(period)

    fsm = _read_rows(fsm_df, "fsm", id_col="payout_id", date_col="collected_date")
    gl = _read_rows(gl_df, "gl", id_col="gl_ref", date_col="gl_date")
    bank = _read_rows(bank_df, "bank", id_col="bank_ref", date_col="settlement_date")

    used: set[tuple[str, int]] = set()
    raw_matches: list[BatchMatch] = []

    def _mark(rows: list[_Row]) -> None:
        for row in rows:
            used.add((row.side, row.index))

    def _free(rows: list[_Row]) -> list[_Row]:
        return [r for r in rows if (r.side, r.index) not in used]

    # ---- Pass 1: exact ID, 1:1 only ---------------------------------------
    all_ids = sorted({r.ref_norm for r in (*fsm, *gl, *bank) if r.ref_norm is not None})
    for id_val in all_ids:
        f_rows = [r for r in fsm if r.ref_norm == id_val]
        g_rows = [r for r in gl if r.ref_norm == id_val]
        b_rows = [r for r in bank if r.ref_norm == id_val]

        if len(f_rows) > 1 or len(g_rows) > 1 or len(b_rows) > 1:
            # (c) ambiguous ID — never pick one.
            raw_matches.append(
                _emit_ambiguous(
                    match_id=build_match_id("id", id_val=id_val),
                    match_kind="id",
                    candidate_count=max(len(f_rows), len(g_rows), len(b_rows)),
                )
            )
            _mark([*f_rows, *g_rows, *b_rows])
            continue

        if len(f_rows) + len(g_rows) + len(b_rows) < 2:
            continue  # id lives on only one side; leave for fallback / leftovers

        # (a) exact unique ID match across the sides that have it
        raw_matches.append(
            _emit(
                match_id=build_match_id("id", id_val=id_val),
                match_kind="id",
                fsm=f_rows[0] if f_rows else None,
                gl=g_rows[0] if g_rows else None,
                bank=b_rows[0] if b_rows else None,
            )
        )
        _mark([*f_rows, *g_rows, *b_rows])

    # ---- Pass 2: fallback exact net + same calendar date -------------------
    # Dollar: exact equality after round(2). Date: equality, 0-day window.
    groups: dict[tuple[float, date], list[_Row]] = {}
    for row in _free([*fsm, *gl, *bank]):
        amount, day = row.key_amount, row.day
        if amount is None or day is None:
            continue
        groups.setdefault((amount, day), []).append(row)

    for amount, day in sorted(groups):
        members = groups[(amount, day)]
        nf = sum(1 for r in members if r.side == "fsm")
        ng = sum(1 for r in members if r.side == "gl")
        nb = sum(1 for r in members if r.side == "bank")
        if nf + ng + nb < 2:
            continue

        if nf <= 1 and ng <= 1 and nb <= 1:
            # (b) at most one row per side
            raw_matches.append(
                _emit(
                    match_id=build_match_id("amount_date", amount=amount, day=day),
                    match_kind="amount_date",
                    fsm=next((r for r in members if r.side == "fsm"), None),
                    gl=next((r for r in members if r.side == "gl"), None),
                    bank=next((r for r in members if r.side == "bank"), None),
                )
            )
        else:
            # (c) do NOT pick first / largest / closest
            raw_matches.append(
                _emit_ambiguous(
                    match_id=build_match_id("amount_date", amount=amount, day=day),
                    match_kind="amount_date",
                    candidate_count=max(nf, ng, nb),
                    group_amount=amount,
                    group_day=day,
                )
            )
        _mark(members)

    # ---- Pass 3: leftovers -------------------------------------------------
    # Unused GL-only UF lines are coverage/consolidator territory, not ours.
    unmatched_processor_count = 0
    unmatched_bank_count = 0

    for side, rows in (("fsm", fsm), ("bank", bank)):
        leftovers = sorted(_free(rows), key=lambda r: r.index)
        seq_counter: dict[tuple[float | None, date | None], int] = {}
        for row in leftovers:
            amount = row.key_amount
            seq = None
            if row.ref_norm is None:
                key = (amount, row.day)
                seq = seq_counter.get(key, 0)
                seq_counter[key] = seq + 1
            raw_matches.append(
                _emit(
                    match_id=build_match_id(
                        "none",
                        side=side,
                        ref=row.ref_raw,
                        amount=amount,
                        day=row.day,
                        seq=seq,
                    ),
                    match_kind="none",
                    fsm=row if side == "fsm" else None,
                    gl=None,
                    bank=row if side == "bank" else None,
                )
            )
            if side == "fsm":
                unmatched_processor_count += 1
            else:
                unmatched_bank_count += 1
        _mark(leftovers)

    # ---- Classify ----------------------------------------------------------
    out = [
        classified
        for classified in (
            _classify(m, period_end, uf_account_name) for m in raw_matches
        )
        if classified is not None
    ]

    return MatchResult(
        matches=out,
        unmatched_processor_count=unmatched_processor_count,
        unmatched_bank_count=unmatched_bank_count,
    )


# ---------------------------------------------------------------------------
# Account-level residue (decision E.6)
# ---------------------------------------------------------------------------

# Most action-requiring first. A card must never read "No action required"
# while a batch nested under it needs a JE or a reclass.
_RESIDUE_PRIORITY: tuple[str, ...] = (
    "missing_je",
    "categorical_misclassification",
    "stale_reference",
    "timing_cutoff",
    "structural_explained",
)


def residue_classification(matches: list[BatchMatch]) -> str | None:
    """Pandas-chosen account-level class for an item carrying `matches`."""
    present = {m.classification for m in matches if m.classification is not None}
    for candidate in _RESIDUE_PRIORITY:
        if candidate in present:
            return candidate
    return None
