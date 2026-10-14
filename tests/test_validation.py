"""Input contract tests (roadmap section G; section X 'Invalid ranges/types/dimension keys')."""

from __future__ import annotations

import math

import pytest

from profmatch.models import SectionProfile, StudentPreferences
from profmatch.validation import ValidationError

VALID_WEIGHTS = [1, 1, 1, 1]


def student(values, weights=VALID_WEIGHTS):
    return StudentPreferences.from_lists(values, weights)


def section(values, **overrides):
    fields = dict(
        section_id="PM101-01", course_code="PM101", instructor="Instructor A (fictional)",
        values=values, source="synthetic fixture", is_synthetic=True,
    )
    fields.update(overrides)
    return SectionProfile.from_lists(**fields)


# --------------------------------------------------------------------------- student preferences

@pytest.mark.parametrize(
    "bad",
    [0, 6, -1, 2.5, 3.0, "3", True, False, [3]],
    ids=["zero", "six", "negative", "fraction", "float-3.0", "string", "True", "False", "list"],
)
def test_invalid_preference_values_are_rejected(bad):
    with pytest.raises(ValidationError, match=r"format: preference must be a whole number from 1 to 5"):
        student([bad, 3, 3, 3])


def test_booleans_are_rejected_even_though_true_equals_one():
    assert True == 1  # the Python quirk this guards against
    with pytest.raises(ValidationError, match="bool"):
        student([True, 3, 3, 3])


@pytest.mark.parametrize("bad", [-1, 4, 1.5, True, "2", None])
def test_invalid_weights_are_rejected(bad):
    with pytest.raises(ValidationError, match=r"structure: importance weight must be a whole number"):
        student([3, 3, 3, 3], [1, 1, 1, bad])


def test_no_preference_must_have_weight_zero():
    with pytest.raises(ValidationError, match="assessment: 'No preference'"):
        student([3, None, 3, 3], [1, 2, 1, 1])
    # ...and is accepted with weight 0
    assert student([3, None, 3, 3], [1, 0, 1, 1]).values["assessment"] is None


def test_unknown_dimension_key_gives_helpful_error():
    with pytest.raises(ValidationError, match=r"unknown dimension key.*'formatt'.*Valid dimensions"):
        StudentPreferences(
            {"formatt": 3, "assessment": 3, "collaboration": 3, "structure": 3}, dict.fromkeys(
                ["format", "assessment", "collaboration", "structure"], 1)
        )


def test_missing_dimension_key_is_rejected_not_assumed_unknown():
    with pytest.raises(ValidationError, match="missing dimension.*structure"):
        StudentPreferences(
            {"format": 3, "assessment": 3, "collaboration": 3},
            {"format": 1, "assessment": 1, "collaboration": 1, "structure": 1},
        )


def test_non_mapping_input_is_rejected():
    with pytest.raises(ValidationError, match="must be a mapping"):
        StudentPreferences([3, 3, 3, 3], [1, 1, 1, 1])


def test_from_lists_requires_four_values():
    with pytest.raises(ValidationError, match="Expected 4 values"):
        student([3, 3, 3])


def test_preferences_are_copied_so_later_mutation_has_no_effect():
    values = {"format": 2, "assessment": 5, "collaboration": 1, "structure": 4}
    weights = {"format": 3, "assessment": 3, "collaboration": 2, "structure": 1}
    prefs = StudentPreferences(values, weights)
    values["format"] = 5
    weights["format"] = 0
    assert prefs.values["format"] == 2
    assert prefs.weights["format"] == 3


# --------------------------------------------------------------------------- section profiles

@pytest.mark.parametrize(
    "bad",
    [0, 6, 0.99, 5.01, math.nan, math.inf, True, "3"],
    ids=["zero", "six", "below-1", "above-5", "nan", "inf", "True", "string"],
)
def test_invalid_profile_values_are_rejected(bad):
    with pytest.raises(ValidationError, match=r"collaboration: profile value must be a number from 1 to 5"):
        section([3, 3, bad, 3])


@pytest.mark.parametrize("good", [1, 5, 3.5, 2.0, None])
def test_valid_profile_values_are_accepted(good):
    assert section([3, 3, good, 3]).values["collaboration"] == good


@pytest.mark.parametrize("field", ["section_id", "course_code", "instructor", "source"])
def test_profile_text_fields_must_be_non_empty(field):
    with pytest.raises(ValidationError, match=field):
        section([3, 3, 3, 3], **{field: "  "})


def test_is_synthetic_must_be_a_real_boolean():
    with pytest.raises(ValidationError, match="is_synthetic"):
        section([3, 3, 3, 3], is_synthetic="yes")
