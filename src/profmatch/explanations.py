"""Deterministic explanations built only from the calculation and the profile data.

No language model and no invented facts: every sentence is a template filled with
numbers that already exist in a MatchResult. Same input -> same text, always.

Every question the student rated is explained in exactly one place, so a card can
never hide a mismatch that lowered the score:
- close:    within 1 step of the student's answer (similarity >= 0.75),
            listed by points earned;
- tradeoff: more than 1 step apart (similarity < 0.75), listed by points lost;
- unknown:  the instructor gave no single answer ("Varies / unable to answer" or
            blank), so the question is left out of their score.
Gaps are counted in "steps" between answers so they are not confused with score points.
Sentences say "the instructor answered" because every profile is an instructor's
self-report; revisit the wording if profiles ever combine other sources.
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
from .scale import (
    DIMENSION_LABELS,
    DIMENSIONS,
    IMPORTANCE_LABELS,
    QUESTION_BY_KEY,
    SCALE_SPAN,
    UNKNOWN_ANSWER_LABEL,
)

CLOSE_MAX_GAP = 1
CLOSE_MIN_SIMILARITY = 1 - Fraction(CLOSE_MAX_GAP, SCALE_SPAN)  # 3/4

NOT_A_PREDICTION = (
    "Alignment measures how closely your answers agree with the instructor's answers. "
    "It does not predict grades or how well you will do, and it does not rate teaching quality."
)


@dataclass(frozen=True)
class Explanation:
    section_id: str
    headline: str
    reasons: tuple[str, ...]    # rated questions within 1 step, most points earned first
    tradeoffs: tuple[str, ...]  # rated questions more than 1 step apart, most points lost first
    missing: tuple[str, ...]    # rated questions this instructor gave no single answer to
    details: tuple[str, ...]    # one line per question: the full "Why this result?" breakdown
    calculation: str | None     # the alignment formula with this student's numbers
    caveats: tuple[str, ...]


def _fmt_number(value: int | float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{float(value):g}"


def short_value(dimension: str, value: int | float | None) -> str:
    """'Often'; 'between About half and Often' for a value such as 3.5; 'unknown'."""
    if value is None:
        return "unknown"
    answers = QUESTION_BY_KEY[dimension].answers
    if float(value).is_integer():
        return answers[int(value) - 1][0]
    return f"between {answers[int(value) - 1][0]} and {answers[int(value)][0]}"


def describe_value(dimension: str, value: int | float | None) -> str:
    """'Often (61–80% of class sessions)'; '3.5, between About half and Often'; 'unknown'."""
    if value is None:
        return "unknown"
    if float(value).is_integer():
        return QUESTION_BY_KEY[dimension].answers[int(value) - 1][1]
    return f"{_fmt_number(value)}, {short_value(dimension, value)}"


def format_percent(fraction: Fraction) -> str:
    """Whole-number percentage using the same half-up rule as scores."""
    return f"{round_half_up(fraction * 100)}%"


def _pts(x: Fraction) -> str:
    return f"{float(x):.2f}"


def _steps(d: DimensionResult) -> str:
    gap = abs(d.preference - d.observed)
    return f"{_fmt_number(gap)} step apart" if gap == 1 else f"{_fmt_number(gap)} steps apart"


def _reason(d: DimensionResult) -> str:
    label, importance = DIMENSION_LABELS[d.dimension], IMPORTANCE_LABELS[d.weight]
    if d.similarity == 1:
        return f"Same answer on {label}: {short_value(d.dimension, d.observed)}. You rated this {importance}."
    return (
        f"Close on {label}: you chose {short_value(d.dimension, d.preference)}, the instructor answered "
        f"{short_value(d.dimension, d.observed)} ({_steps(d)}). You rated this {importance}."
    )


def _tradeoff(d: DimensionResult) -> str:
    return (
        f"Tradeoff on {DIMENSION_LABELS[d.dimension]}: you chose {short_value(d.dimension, d.preference)}, "
        f"the instructor answered {short_value(d.dimension, d.observed)} ({_steps(d)}). "
        f"You rated this {IMPORTANCE_LABELS[d.weight]}."
    )


def _missing(d: DimensionResult) -> str:
    return (
        f"Not comparable on {DIMENSION_LABELS[d.dimension]}: this instructor answered "
        f"'{UNKNOWN_ANSWER_LABEL}' or left it blank. You rated this {IMPORTANCE_LABELS[d.weight]}."
    )


def _detail_line(d: DimensionResult) -> str:
    topic = QUESTION_BY_KEY[d.dimension].topic
    instructor = describe_value(d.dimension, d.observed)
    if d.status == NOT_REQUESTED:
        return f"{topic}: no preference, so not used. The instructor answered {instructor}."
    you = describe_value(d.dimension, d.preference)
    if d.status == MISSING:
        return (
            f"{topic}: you chose {you}; the instructor answered '{UNKNOWN_ANSWER_LABEL}' or left it blank. "
            f"Never guessed, so left out of the score (importance {d.weight})."
        )
    points = "point" if d.weight == 1 else "points"
    product = f"similarity {float(d.similarity):.2f} × importance {d.weight} = {_pts(d.contribution)} of {d.weight} {points}"
    if d.similarity == 1:
        return f"{topic}: you and the instructor both answered {you}, so {product}."
    return f"{topic}: you chose {you}; the instructor answered {instructor}. {_steps(d).capitalize()}, so {product}."


def _calculation(result: MatchResult) -> str | None:
    if result.alignment is None:
        return None
    earned = sum((d.contribution for d in result.dimensions if d.status == SCORED), Fraction(0))
    scope = "" if result.status == COMPLETE else ", counting only the questions this instructor answered"
    return (
        f"Alignment = 100 × points earned ÷ points possible{scope} = 100 × {_pts(earned)} ÷ "
        f"{result.known_weight} = {float(result.alignment):.1f}, shown as {result.display_score}."
    )


def _headline(result: MatchResult) -> str:
    if result.status == NO_PREFERENCES:
        return "No score: every question is set to 'No preference'."
    if result.status == INSUFFICIENT_EVIDENCE:
        return "No score: this instructor gave no single answer on any question you rated."
    if result.status == PARTIAL:
        missing = ", ".join(DIMENSION_LABELS[d] for d in result.missing_dimensions)
        return (
            f"Not ranked: no single answer on {missing}. On the questions it can be compared on "
            f"({format_percent(result.coverage)} of your importance weight), alignment is "
            f"{result.display_score}/100, which can't be compared fairly with fully answered sections."
        )
    if result.status == COMPLETE:
        rated = sum(1 for d in result.dimensions if d.status == SCORED)
        scope = "the one question you rated" if rated == 1 else f"all {rated} questions you rated"
        return f"Alignment {result.display_score}/100 across {scope}."
    raise ValueError(f"Unknown status {result.status!r}")  # defensive: new status added without template


def explain(result: MatchResult) -> Explanation:
    scored = [d for d in result.dimensions if d.status == SCORED]
    close = sorted(
        (d for d in scored if d.similarity >= CLOSE_MIN_SIMILARITY),
        key=lambda d: (-d.contribution, DIMENSIONS.index(d.dimension)),
    )
    far = sorted(
        (d for d in scored if d.similarity < CLOSE_MIN_SIMILARITY),
        key=lambda d: (-d.lost, DIMENSIONS.index(d.dimension)),
    )
    caveats = [NOT_A_PREDICTION, f"Instructor answers: {result.profile.source}."]
    if result.profile.is_synthetic:
        caveats.insert(0, "SYNTHETIC: fictional data used for demonstration only.")
    return Explanation(
        section_id=result.section_id,
        headline=_headline(result),
        reasons=tuple(_reason(d) for d in close),
        tradeoffs=tuple(_tradeoff(d) for d in far),
        missing=tuple(_missing(d) for d in result.dimensions if d.status == MISSING),
        details=tuple(_detail_line(d) for d in result.dimensions),
        calculation=_calculation(result),
        caveats=tuple(caveats),
    )


__all__ = [
    "CLOSE_MAX_GAP",
    "Explanation",
    "NOT_A_PREDICTION",
    "describe_value",
    "explain",
    "format_percent",
    "short_value",
]
