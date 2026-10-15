"""Explanation tests: deterministic, derived from the calculation, no forced positives."""

from __future__ import annotations

import pytest

from profmatch.demo import main
from profmatch.explanations import NOT_A_PREDICTION, describe_value, explain
from profmatch.matching import compare_sections, score_section
from profmatch.models import SectionProfile, StudentPreferences
from profmatch.synthetic import (
    DEMO_STUDENTS,
    PM101_SECTIONS,
    SECTION_A,
    SECTION_B,
    SECTION_C,
    STUDENT_1,
    STUDENT_2,
)


def all_text(exp):
    return " ".join([exp.headline, *exp.reasons, exp.tradeoff or "", *exp.missing, *exp.details, *exp.caveats])


@pytest.mark.parametrize(
    "dimension, value, expected",
    [
        ("format", 1, "1 (mostly lecture)"),
        ("format", 2, "2 (between mostly lecture and roughly balanced)"),
        ("structure", 5, "5 (detailed schedules/instructions in advance)"),
        ("collaboration", 3.5, "3.5 (between mixed and mostly group work)"),
        ("assessment", 3.0, "3 (a mixture)"),
        ("assessment", None, "unknown"),
    ],
)
def test_describe_value_uses_section_g_anchors(dimension, value, expected):
    assert describe_value(dimension, value) == expected


def test_a_for_student_1_gives_two_reasons_ordered_by_points_earned_and_no_tradeoff():
    exp = explain(score_section(STUDENT_1, SECTION_A))
    assert exp.headline.startswith("Alignment 89/100")
    assert len(exp.reasons) == 2
    assert "class format" in exp.reasons[0]           # earned 3.00 points
    assert "assessment distribution" in exp.reasons[1]  # earned 2.25 points
    assert exp.tradeoff is None
    assert exp.missing == ()


def test_b_for_student_1_has_no_forced_positive_reasons():
    exp = explain(score_section(STUDENT_1, SECTION_B))
    assert exp.reasons == ()
    assert "class format" in exp.tradeoff  # ties with assessment at 2.25 lost; dimension order breaks it
    assert "3-point gap on something you rated very important" in exp.tradeoff


def test_c_for_student_1_explains_why_it_is_not_ranked():
    exp = explain(score_section(STUDENT_1, SECTION_C))
    assert exp.headline.startswith("Not ranked: more information needed (assessment distribution)")
    assert "67%" in exp.headline
    assert len(exp.missing) == 1 and "assessment distribution" in exp.missing[0]
    assessment_line = exp.details[1]
    assert "unknown" in assessment_line and "not assumed neutral" in assessment_line


def test_tradeoff_is_the_costliest_mismatch_not_the_biggest_gap():
    # format: 2-point gap, very important -> loses 3 * 0.5  = 1.50 points
    # structure: 3-point gap, slightly important -> loses 1 * 0.25 = 0.75 points
    student = StudentPreferences.from_lists([1, None, None, 5], [3, 0, 0, 1])
    section = SectionProfile.from_lists("S-01", "PM101", "Instructor S (fictional)",
                                        [3, 3, 3, 2], "synthetic fixture", True)
    exp = explain(score_section(student, section))
    assert exp.tradeoff.startswith("Tradeoff on class format")
    assert "2-point gap" in exp.tradeoff


def test_insufficient_evidence_explanation():
    empty = SectionProfile.from_lists("PM101-09", "PM101", "Instructor Z (fictional)",
                                      [None] * 4, "synthetic fixture", True)
    exp = explain(score_section(STUDENT_1, empty))
    assert "insufficient evidence" in exp.headline
    assert exp.reasons == () and exp.tradeoff is None
    assert len(exp.missing) == 4


def test_no_preferences_explanation_is_descriptive_only():
    nothing = StudentPreferences.from_lists([None] * 4, [0] * 4)
    exp = explain(score_section(nothing, SECTION_A))
    assert "No score" in exp.headline
    assert exp.reasons == () and exp.tradeoff is None
    assert all("not used in the score" in line for line in exp.details)


def test_explanations_are_deterministic():
    for prefs in DEMO_STUDENTS.values():
        for profile in PM101_SECTIONS:
            assert explain(score_section(prefs, profile)) == explain(score_section(prefs, profile))


def test_required_caveats_are_present():
    exp = explain(score_section(STUDENT_1, SECTION_A))
    assert NOT_A_PREDICTION in exp.caveats
    assert any(c.startswith("SYNTHETIC") for c in exp.caveats)
    assert any("Evidence source" in c for c in exp.caveats)


@pytest.mark.parametrize("word", ["probability", "success", "proven", "best", "worst", "guarantee"])
def test_explanations_avoid_forbidden_claims(word):
    # Section F: say "alignment score", never "probability of success" or rankings of professors.
    for prefs in DEMO_STUDENTS.values():
        for result in compare_sections(prefs, PM101_SECTIONS).all_results:
            assert word not in all_text(explain(result)).lower()


# --------------------------------------------------------------------------- command-line demo

def test_demo_runs_and_prints_the_worked_numbers(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC DEMO" in out
    for expected in ["88.889", "27.778", "95.833", "100.000", "Eligible to rank", "no (partial)"]:
        assert expected in out


def test_demo_accepts_custom_preferences(capsys):
    assert main(["--prefs", "2,-,1,4", "--weights", "3,0,2,1"]) == 0
    assert "Custom student" in capsys.readouterr().out


def test_demo_reports_invalid_input_cleanly(capsys):
    assert main(["--prefs", "2,9,1,4", "--weights", "3,3,2,1"]) == 2
    assert "assessment: preference must be a whole number" in capsys.readouterr().err
