"""The matching engine (roadmap section H). Pure functions: no Streamlit, no database.

For student preference p_j, profile value x_j and importance weight w_j:

    similarity_j = 1 - |p_j - x_j| / 4
    W            = sum of all weights
    K            = rated dimensions (w_j > 0) whose profile value is known
    W_known      = sum of weights in K
    alignment    = 100 * sum(w_j * similarity_j for j in K) / W_known
    coverage     = W_known / W

Arithmetic is exact (fractions.Fraction), so 8/9 stays 8/9 instead of
0.8888888888888888. That makes rounding and tie detection deterministic: no score
can land on the wrong side of a .5 boundary because of floating-point error.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from .models import SectionProfile, StudentPreferences
from .scale import DIMENSIONS, SCALE_SPAN
from .validation import ValidationError

# Identifies the scoring + missingness + ranking policy. Bump it whenever any of
# those rules change, so evaluation results from different policies never mix.
METHOD_VERSION = "m0-weighted-distance-complete-only-v1"

# Per-dimension status
SCORED = "scored"                # rated (w > 0) and the section has a value
MISSING = "missing"              # rated, but the section has no usable value
NOT_REQUESTED = "not_requested"  # weight 0: does not affect the score

# Per-section status
COMPLETE = "complete"                            # evidence for every rated dimension
PARTIAL = "partial"                              # evidence for some rated dimensions
INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # evidence for none of them
NO_PREFERENCES = "no_preferences"                # student rated nothing (W = 0)

# Whole-comparison mode
MODE_RANKED = "ranked"                            # 2+ complete sections
MODE_SINGLE_OPTION = "single_option"              # exactly 1 complete section: no real ranking
MODE_UNRANKED_INCOMPLETE = "unranked_incomplete"  # W > 0 but no complete sections
MODE_NO_PREFERENCES = "no_preferences"            # W = 0: descriptive comparison only
MODE_NO_SECTIONS = "no_sections"                  # nothing to compare


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    preference: int | None
    observed: int | float | None
    weight: int
    status: str
    similarity: Fraction | None    # None unless SCORED
    contribution: Fraction | None  # w * similarity: points earned
    lost: Fraction | None          # w * (1 - similarity): points lost to mismatch


@dataclass(frozen=True)
class MatchResult:
    profile: SectionProfile
    dimensions: tuple[DimensionResult, ...]
    total_weight: int             # W
    known_weight: int             # W_known
    alignment: Fraction | None    # exact, unrounded, 0..100
    coverage: Fraction | None     # W_known / W, None when W = 0
    status: str

    @property
    def section_id(self) -> str:
        return self.profile.section_id

    @property
    def display_score(self) -> int | None:
        """Whole-number score for display. Ranking uses this, not the exact value."""
        return None if self.alignment is None else round_half_up(self.alignment)

    @property
    def eligible_for_ranking(self) -> bool:
        return self.status == COMPLETE

    @property
    def missing_dimensions(self) -> tuple[str, ...]:
        return tuple(d.dimension for d in self.dimensions if d.status == MISSING)


@dataclass(frozen=True)
class RankedEntry:
    rank: int
    result: MatchResult


@dataclass(frozen=True)
class Comparison:
    mode: str
    ranked: tuple[RankedEntry, ...]          # complete sections only, best first
    needs_more_info: tuple[MatchResult, ...] # partial / insufficient, by section ID (not by score)
    all_results: tuple[MatchResult, ...]     # every section, by section ID
    method_version: str = METHOD_VERSION


def similarity(preference: int, observed: int | float) -> Fraction:
    """1 for identical answers, 0 for opposite ends of the scale."""
    return 1 - abs(Fraction(preference) - Fraction(observed)) / SCALE_SPAN


def round_half_up(value: Fraction) -> int:
    """Round .5 upward. Python's built-in round() uses banker's rounding,
    so round(62.5) == 62 and round(63.5) == 64 — inconsistent for display."""
    return math.floor(value + Fraction(1, 2))


def score_section(prefs: StudentPreferences, profile: SectionProfile) -> MatchResult:
    """Score one section against one student's preferences."""
    if not isinstance(prefs, StudentPreferences):
        raise ValidationError(f"Expected StudentPreferences, got {type(prefs).__name__}.")
    if not isinstance(profile, SectionProfile):
        raise ValidationError(f"Expected SectionProfile, got {type(profile).__name__}.")

    dims: list[DimensionResult] = []
    earned = Fraction(0)
    known_weight = 0

    for d in DIMENSIONS:
        p, x, w = prefs.values[d], profile.values[d], prefs.weights[d]
        if w == 0:
            dims.append(DimensionResult(d, p, x, w, NOT_REQUESTED, None, None, None))
        elif x is None:
            # Unknown stays unknown: never 0, never an imputed midpoint of 3.
            dims.append(DimensionResult(d, p, x, w, MISSING, None, None, None))
        else:
            s = similarity(p, x)
            dims.append(DimensionResult(d, p, x, w, SCORED, s, w * s, w * (1 - s)))
            earned += w * s
            known_weight += w

    total_weight = prefs.total_weight
    if total_weight == 0:
        alignment, coverage, status = None, None, NO_PREFERENCES
    elif known_weight == 0:
        alignment, coverage, status = None, Fraction(0), INSUFFICIENT_EVIDENCE
    else:
        alignment = 100 * earned / known_weight
        coverage = Fraction(known_weight, total_weight)
        status = COMPLETE if known_weight == total_weight else PARTIAL

    return MatchResult(profile, tuple(dims), total_weight, known_weight, alignment, coverage, status)


def compare_sections(
    prefs: StudentPreferences, profiles: Iterable[SectionProfile]
) -> Comparison:
    """Score every section and apply the conservative ranking policy.

    - Only COMPLETE sections are ranked. A partial score can look higher simply
      because the dimension it is missing would have been a mismatch, so partial
      sections go to a separate "more information needed" group, sorted by ID.
    - Ranking uses the displayed whole-number score. Sections with the same
      displayed score share a rank (competition ranking: 1, 2, 2, 4) and are
      listed by section ID, so tiny decimal differences never imply a winner.
    """
    profiles = tuple(profiles)
    _check_comparable(profiles)

    results = tuple(sorted((score_section(prefs, p) for p in profiles), key=lambda r: r.section_id))

    if not results:
        return Comparison(MODE_NO_SECTIONS, (), (), ())
    if prefs.total_weight == 0:
        return Comparison(MODE_NO_PREFERENCES, (), (), results)

    complete = sorted(
        (r for r in results if r.status == COMPLETE),
        key=lambda r: (-r.display_score, r.section_id),
    )
    needs_more_info = tuple(r for r in results if r.status != COMPLETE)  # already in ID order

    ranked: list[RankedEntry] = []
    for position, result in enumerate(complete, start=1):
        tied_with_previous = ranked and ranked[-1].result.display_score == result.display_score
        rank = ranked[-1].rank if tied_with_previous else position
        ranked.append(RankedEntry(rank, result))

    if len(ranked) >= 2:
        mode = MODE_RANKED
    elif len(ranked) == 1:
        mode = MODE_SINGLE_OPTION
    else:
        mode = MODE_UNRANKED_INCOMPLETE
    return Comparison(mode, tuple(ranked), needs_more_info, results)


def _check_comparable(profiles: tuple[SectionProfile, ...]) -> None:
    for p in profiles:
        if not isinstance(p, SectionProfile):
            raise ValidationError(f"Expected SectionProfile, got {type(p).__name__}.")
    ids = [p.section_id for p in profiles]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValidationError(f"Duplicate section ID(s): {', '.join(duplicates)}.")
    courses = sorted({p.course_code for p in profiles})
    if len(courses) > 1:
        raise ValidationError(
            f"Sections from different courses cannot be compared together: {', '.join(courses)}."
        )
    if len({p.is_synthetic for p in profiles}) > 1:
        raise ValidationError(
            "Synthetic and real profiles cannot be mixed in one comparison. "
            "Run synthetic demo data and pilot data as separate datasets."
        )
