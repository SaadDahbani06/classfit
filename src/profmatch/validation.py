"""Strict input validation for preferences, weights and profile values (roadmap section G).

Policy: reject invalid input with a message that names the dimension and the
problem. Never coerce silently (e.g. "3" -> 3, 2.5 -> 3, True -> 1).

Why booleans get special treatment: in Python, ``bool`` is a subclass of ``int``,
so ``isinstance(True, int)`` is True and ``True == 1``. Without an explicit check,
a checkbox value could slip into the scorer as a survey answer of 1.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .scale import DIMENSIONS, SCALE_MAX, SCALE_MIN, WEIGHT_MAX, WEIGHT_MIN


class ValidationError(ValueError):
    """Input violates the engine's input contract."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_real(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _describe(value: Any) -> str:
    return f"{value!r} ({type(value).__name__})"


def check_dimension_keys(mapping: Any, what: str) -> None:
    """Require exactly the known dimension keys (scale.DIMENSIONS).

    Missing keys are rejected rather than treated as unknown: an unknown value
    must be stated explicitly as ``None`` so that "we forgot to supply it" and
    "we have no evidence" cannot be confused.
    """
    if not isinstance(mapping, Mapping):
        raise ValidationError(
            f"{what} must be a mapping of dimension -> value, got {type(mapping).__name__}."
        )
    unknown = [k for k in mapping if k not in DIMENSIONS]
    if unknown:
        raise ValidationError(
            f"{what} has unknown dimension key(s) {sorted(map(repr, unknown))}. "
            f"Valid dimensions: {', '.join(DIMENSIONS)}."
        )
    missing = [d for d in DIMENSIONS if d not in mapping]
    if missing:
        raise ValidationError(
            f"{what} is missing dimension(s): {', '.join(missing)}. "
            "Use None to state that a value is unknown or that there is no preference."
        )


def validate_preference_value(dimension: str, value: Any) -> int | None:
    """A student's answer: a whole number 1-5, or None for 'No preference'."""
    if value is None:
        return None
    if not _is_int(value) or not SCALE_MIN <= value <= SCALE_MAX:
        raise ValidationError(
            f"{dimension}: preference must be a whole number from {SCALE_MIN} to {SCALE_MAX}, "
            f"or None for 'No preference'; got {_describe(value)}."
        )
    return value


def validate_weight(dimension: str, value: Any) -> int:
    """Importance: a whole number 0 (no preference) to 3 (very important)."""
    if not _is_int(value) or not WEIGHT_MIN <= value <= WEIGHT_MAX:
        raise ValidationError(
            f"{dimension}: importance weight must be a whole number from {WEIGHT_MIN} "
            f"(no preference) to {WEIGHT_MAX} (very important); got {_describe(value)}."
        )
    return value


def validate_profile_value(dimension: str, value: Any) -> int | float | None:
    """A section's observed value: a real number in [1, 5], or None for unknown.

    Unlike student answers, profile values may be non-integers because a median
    of an even number of reports can fall halfway between two answers (e.g. 3.5).
    """
    if value is None:
        return None
    if not _is_real(value) or not math.isfinite(value) or not SCALE_MIN <= value <= SCALE_MAX:
        raise ValidationError(
            f"{dimension}: profile value must be a number from {SCALE_MIN} to {SCALE_MAX}, "
            f"or None if unknown; got {_describe(value)}. Unknown values must be None, "
            "never 0 or a guessed midpoint."
        )
    return value


def validate_preferences(values: Any) -> dict[str, int | None]:
    check_dimension_keys(values, "Preferences")
    return {d: validate_preference_value(d, values[d]) for d in DIMENSIONS}


def validate_weights(weights: Any) -> dict[str, int]:
    check_dimension_keys(weights, "Importance weights")
    return {d: validate_weight(d, weights[d]) for d in DIMENSIONS}


def validate_profile_values(values: Any) -> dict[str, int | float | None]:
    check_dimension_keys(values, "Profile values")
    return {d: validate_profile_value(d, values[d]) for d in DIMENSIONS}


def validate_preferences_and_weights(
    values: Any, weights: Any
) -> tuple[dict[str, int | None], dict[str, int]]:
    """Validate both and check they agree: 'No preference' must carry weight 0."""
    clean_values = validate_preferences(values)
    clean_weights = validate_weights(weights)
    for d in DIMENSIONS:
        if clean_values[d] is None and clean_weights[d] != 0:
            raise ValidationError(
                f"{d}: 'No preference' (None) must have importance weight 0; "
                f"got weight {clean_weights[d]}. Either answer the question or set its weight to 0."
            )
    return clean_values, clean_weights
