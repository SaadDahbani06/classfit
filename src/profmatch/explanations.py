"""Deterministic explanations built only from the calculation and the profile data.

No language model and no invented facts: every sentence is a template filled with
numbers that already exist in a MatchResult. Same input -> same text, always.

Thresholds (project decisions, documented so they can be defended or changed):
- A "reason" is a rated dimension within 1 scale point (similarity >= 0.75).
  At most two are shown, those that earned the most points. If none qualify,
  no reasons are shown — we do not manufacture positives.
- A "tradeoff" is a rated dimension 2+ scale points apart (similarity <= 0.5).
  The one that cost the most points is shown.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .matching import (
    COMPLETE,
    INSUFFICIENT_EVIDENCE,
    MISSING,
    NO_PREFERENCES,
    NOT_REQUESTED,
    PARTIAL,
    SCORED,
    DimensionResult,
    MatchResult,
    round_half_up,
)
from .scale import DIMENSION_LABELS, DIMENSIONS, IMPORTANCE_LABELS, SCALE_ANCHORS

REASON_MIN_SIMILARITY = Fraction(3, 4)
TRADEOFF_MAX_SIMILARITY = Fraction(1, 2)
MAX_REASONS = 2

NOT_A_PREDICTION = "Alignment reflects your stated preferences only. It is not a grade prediction."
NO_CLOSE_MATCH = "No dimension you rated is within 1 point of your preference."


@dataclass(frozen=True)
class Explanation:
    section_id: str
    headline: str
    reasons: tuple[str, ...]
    tradeoff: str | None
    missing: tuple[str, ...]
    details: tuple[str, ...]   # one line per dimension: the full "Why this result?" breakdown
    caveats: tuple[str, ...]


def _fmt_number(value: int | float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def describe_value(dimension: str, value: int | float | None) -> str:
    """'2 (between mostly lecture and roughly balanced)', '5 (mostly group work)', 'unknown'."""
    if value is None:
        return "unknown"
    anchors = SCALE_ANCHORS[dimension]
    if value in anchors:
        return f"{_fmt_number(value)} ({anchors[int(value)]})"
    points = sorted(anchors)
    low = max(a for a in points if a < value)
    high = min(a for a in points if a > value)
    return f"{_fmt_number(value)} (between {anchors[low]} and {anchors[high]})"


def _importance(weight: int) -> str:
    return f"{IMPORTANCE_LABELS[weight]} ({weight})"


def _pts(x: Fraction) -> str:
    return f"{float(x):.2f}"


def _of_points(n: int) -> str:
    return f"of {n} point" if n == 1 else f"of {n} points"


def format_percent(fraction: Fraction) -> str:
    """Whole-number percentage using the same half-up rule as scores."""
    return f"{round_half_up(fraction * 100)}%"


def _gap(d: DimensionResult) -> str:
    gap = abs(d.preference - d.observed)
    return f"{_fmt_number(gap)}-point gap"


def _detail_line(d: DimensionResult) -> str:
    label = DIMENSION_LABELS[d.dimension].capitalize()
    section = describe_value(d.dimension, d.observed)
    if d.status == NOT_REQUESTED:
        return f"{label}: no preference, not used in the score. This section: {section}."
    you = describe_value(d.dimension, d.preference)
    if d.status == MISSING:
        return (
            f"{label}: you {you}; this section: unknown (no usable evidence, not assumed neutral). "
            f"Importance {_importance(d.weight)}. Excluded from the score."
        )
    values = (
        f"you and this section both {you}"
        if d.preference == d.observed
        else f"you {you}; this section {section}"
    )
    return (
        f"{label}: {values}. Importance {_importance(d.weight)}. "
        f"Similarity {float(d.similarity):.2f} -> {_pts(d.contribution)} {_of_points(d.weight)}."
    )


def _reasons(result: MatchResult) -> tuple[str, ...]:
    candidates = [
        d for d in result.dimensions if d.status == SCORED and d.similarity >= REASON_MIN_SIMILARITY
    ]
    candidates.sort(key=lambda d: (-d.contribution, DIMENSIONS.index(d.dimension)))
    reasons = []
    for d in candidates[:MAX_REASONS]:
        label = DIMENSION_LABELS[d.dimension]
        if d.similarity == 1:
            reasons.append(
                f"Matches your preference on {label}: {describe_value(d.dimension, d.observed)}. "
                f"You rated this {IMPORTANCE_LABELS[d.weight]}."
            )
        else:
            reasons.append(
                f"Close to your preference on {label}: you {_fmt_number(d.preference)}, "
                f"this section {describe_value(d.dimension, d.observed)}. "
                f"You rated this {IMPORTANCE_LABELS[d.weight]}."
            )
    return tuple(reasons)


def _tradeoff(result: MatchResult) -> str | None:
    candidates = [
        d for d in result.dimensions if d.status == SCORED and d.similarity <= TRADEOFF_MAX_SIMILARITY
    ]
    if not candidates:
        return None
    # The mismatch that cost the most weighted points, not simply the biggest gap.
    d = min(candidates, key=lambda d: (-d.lost, DIMENSIONS.index(d.dimension)))
    return (
        f"Tradeoff on {DIMENSION_LABELS[d.dimension]}: you prefer "
        f"{describe_value(d.dimension, d.preference)}; this section is "
        f"{describe_value(d.dimension, d.observed)}. That's a {_gap(d)} on something you rated "
        f"{IMPORTANCE_LABELS[d.weight]}."
    )


def _missing_lines(result: MatchResult) -> tuple[str, ...]:
    return tuple(
        f"No usable evidence on {DIMENSION_LABELS[d.dimension]}, which you rated "
        f"{IMPORTANCE_LABELS[d.weight]}."
        for d in result.dimensions
        if d.status == MISSING
    )


def _headline(result: MatchResult) -> str:
    if result.status == NO_PREFERENCES:
        return "No score: every dimension is marked 'No preference'. Descriptive comparison only."
    if result.status == INSUFFICIENT_EVIDENCE:
        return "No score: insufficient evidence. No data on any dimension you rated."
    if result.status == PARTIAL:
        missing = ", ".join(DIMENSION_LABELS[d] for d in result.missing_dimensions)
        return (
            f"Not ranked: more information needed ({missing}). Partial alignment "
            f"{result.display_score}/100 based on {format_percent(result.coverage)} of your importance "
            "weight; it cannot be compared fairly with fully documented sections."
        )
    if result.status == COMPLETE:
        return (
            f"Alignment {result.display_score}/100. Evidence covers every dimension you rated "
            f"({format_percent(result.coverage)} coverage)."
        )
    raise ValueError(f"Unknown status {result.status!r}")  # defensive: new status added without template


def explain(result: MatchResult) -> Explanation:
    caveats = [NOT_A_PREDICTION, f"Evidence source: {result.profile.source}."]
    if result.profile.is_synthetic:
        caveats.insert(0, "SYNTHETIC: fictional data used for demonstration only.")
    scored = result.status in (COMPLETE, PARTIAL)
    return Explanation(
        section_id=result.section_id,
        headline=_headline(result),
        reasons=_reasons(result) if scored else (),
        tradeoff=_tradeoff(result) if scored else None,
        missing=_missing_lines(result),
        details=tuple(_detail_line(d) for d in result.dimensions),
        caveats=tuple(caveats),
    )


__all__ = [
    "Explanation",
    "NOT_A_PREDICTION",
    "NO_CLOSE_MATCH",
    "describe_value",
    "explain",
    "format_percent",
]
