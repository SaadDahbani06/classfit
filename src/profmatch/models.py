"""Input data types. Both validate themselves on construction, so an invalid
StudentPreferences or SectionProfile cannot exist anywhere in the program."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .scale import DIMENSIONS
from .validation import (
    ValidationError,
    validate_preferences_and_weights,
    validate_profile_values,
)


@dataclass(frozen=True)
class StudentPreferences:
    """What one student wants (p_j) and how much each dimension matters (w_j).

    values:  dimension -> 1..5, or None for "No preference"
    weights: dimension -> 0..3 (0 = no preference, 3 = very important)
    """

    values: dict[str, int | None]
    weights: dict[str, int]

    def __post_init__(self) -> None:
        clean_values, clean_weights = validate_preferences_and_weights(self.values, self.weights)
        # frozen=True blocks normal assignment, so store validated copies this way.
        # Copies also protect us if the caller later mutates the dicts they passed in.
        object.__setattr__(self, "values", clean_values)
        object.__setattr__(self, "weights", clean_weights)

    @classmethod
    def from_lists(
        cls, values: Sequence[int | None], weights: Sequence[int]
    ) -> StudentPreferences:
        """Build from lists in DIMENSIONS order: discussion, practice, plan, balance, exams, collaboration."""
        if len(values) != len(DIMENSIONS) or len(weights) != len(DIMENSIONS):
            raise ValidationError(
                f"Expected {len(DIMENSIONS)} values and {len(DIMENSIONS)} weights in the order "
                f"{', '.join(DIMENSIONS)}; got {len(values)} and {len(weights)}."
            )
        return cls(dict(zip(DIMENSIONS, values)), dict(zip(DIMENSIONS, weights)))

    @property
    def total_weight(self) -> int:
        """W in the roadmap's notation."""
        return sum(self.weights.values())


@dataclass(frozen=True)
class SectionProfile:
    """What we know about one section (x_j), plus where that knowledge came from.

    values: dimension -> number in [1, 5], or None when there is no usable evidence.
    source: human-readable provenance shown in explanations. M2 will replace this
            single string with per-dimension evidence (source type, term, n, spread).
    """

    section_id: str
    course_code: str
    instructor: str
    values: dict[str, int | float | None]
    source: str
    is_synthetic: bool

    def __post_init__(self) -> None:
        for name in ("section_id", "course_code", "instructor", "source"):
            text = getattr(self, name)
            if not isinstance(text, str) or not text.strip():
                raise ValidationError(f"SectionProfile.{name} must be a non-empty string; got {text!r}.")
        if not isinstance(self.is_synthetic, bool):
            raise ValidationError(
                f"SectionProfile.is_synthetic must be True or False; got {self.is_synthetic!r}."
            )
        object.__setattr__(self, "values", validate_profile_values(self.values))

    @classmethod
    def from_lists(
        cls,
        section_id: str,
        course_code: str,
        instructor: str,
        values: Sequence[int | float | None],
        source: str,
        is_synthetic: bool,
    ) -> SectionProfile:
        if len(values) != len(DIMENSIONS):
            raise ValidationError(
                f"Expected {len(DIMENSIONS)} profile values in the order {', '.join(DIMENSIONS)}; "
                f"got {len(values)}."
            )
        return cls(section_id, course_code, instructor, dict(zip(DIMENSIONS, values)), source, is_synthetic)
