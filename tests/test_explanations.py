"""Explanation tests: deterministic, derived from the calculation, consistent with the score."""

from __future__ import annotations

import pytest

from profmatch.demo import main
from profmatch.explanations import (
    CLOSE_MAX_GAP,
    NOT_A_PREDICTION,
    describe_value,
    explain,
    short_value,
)
from profmatch.matching import SCORED, compare_sections, score_section
from profmatch.models import SectionProfile, StudentPreferences
from profmatch.scale import DIMENSION_LABELS, DIMENSIONS, UNKNOWN_ANSWER_LABEL
from profmatch.synthetic import (
    DEMO_STUDENTS,
    PM101_SECTIONS,
    SECTION_B,
    SECTION_C,
    STUDENT_1,
    STUDENT_2,
)


def all_text(exp):
    return " ".join([exp.headline, *exp.reasons, *exp.tradeoffs, *exp.missing, *exp.details,
                     exp.calculation or "", *exp.caveats])


def every_result():
    extra = [
        SectionProfile.from_lists("PM101-08", "PM101", "Instructor Y (fictional)", [1, 1, 1, 1, 1, 1], "synthetic", True),
        SectionProfile.from_lists("PM101-09", "PM101", "Instructor Z (fictional)", [None] * 6, "synthetic", True),
    ]
    for prefs in DEMO_STUDENTS.values():
        yield from compare_sections(prefs, [*PM101_SECTIONS, *extra]).all_results


@pytest.mark.parametrize(
    "dimension, value, expected",
    [
        ("discussion", 1, "Rarely (0–20% of class sessions)"),
        ("exams", 3, "41–60% of the course grade"),
        ("plan", 5, "Followed closely (a detailed dated schedule, kept as published)"),
        ("collaboration", 3.0, "41–60% of the course grade"),
        ("practice", 3.5, "3.5, between About half and Most"),
        ("balance", None, "unknown"),
    ],
)
def test_describe_value_uses_the_full_answer_labels(dimension, value, expected):
    assert describe_value(dimension, value) == expected


@pytest.mark.parametrize(
    "dimension, value, expected",
    [("discussion", 4, "Often"), ("exams", 1, "0–20%"), ("plan", 2.5, "between Changes often and Changes sometimes"),
     ("balance", None, "unknown")],
)
def test_short_value(dimension, value, expected):
    assert short_value(dimension, value) == expected


def test_top_match_for_student_1_lists_close_answers_and_its_tradeoff():
    exp = explain(score_section(STUDENT_1, SECTION_B))
    assert exp.headline == "Alignment 91/100 across all 5 questions you rated."
    assert [r.split(":")[0] for r in exp.reasons] == [
        "Same answer on class discussion",       # 3.00 points earned (ties with exams; question order breaks it)
        "Same answer on timed quizzes and exams",
        "Same answer on concepts and applications",
        "Close on collaborative graded work",    # 1 step apart: 1.50 of 2 points
    ]
    assert exp.tradeoffs == (
        "Tradeoff on guided practice: you chose About half, the instructor answered Little (2 steps apart). "
        "You rated this slightly important.",
    )
    assert exp.missing == ()
    assert exp.calculation == "Alignment = 100 × points earned ÷ points possible = 100 × 10.00 ÷ 11 = 90.9, shown as 91."


def test_every_rated_question_is_explained_exactly_once():
    for result in every_result():
        exp = explain(result)
        lines = [*exp.reasons, *exp.tradeoffs, *exp.missing]
        for d in result.dimensions:
            mentions = sum(DIMENSION_LABELS[d.dimension] in line for line in lines)
            assert mentions == (1 if d.weight > 0 else 0), (result.section_id, d.dimension)


def test_close_and_tradeoff_lines_agree_with_the_engine():
    for result in every_result():
        exp = explain(result)
        scored = [d for d in result.dimensions if d.status == SCORED]
        close = [d for d in scored if abs(d.preference - d.observed) <= CLOSE_MAX_GAP]
        far = [d for d in scored if abs(d.preference - d.observed) > CLOSE_MAX_GAP]
        assert [DIMENSION_LABELS[d.dimension] in line for d, line in zip(
            sorted(close, key=lambda d: (-d.contribution, DIMENSIONS.index(d.dimension))), exp.reasons)] == \
            [True] * len(close)
        assert [DIMENSION_LABELS[d.dimension] in line for d, line in zip(
            sorted(far, key=lambda d: (-d.lost, DIMENSIONS.index(d.dimension))), exp.tradeoffs)] == [True] * len(far)
        assert len(exp.reasons) == len(close) and len(exp.tradeoffs) == len(far)


def test_calculation_line_reproduces_the_score():
    for result in every_result():
        exp = explain(result)
        if result.alignment is None:
            assert exp.calculation is None
        else:
            assert exp.calculation.endswith(
                f"÷ {result.known_weight} = {float(result.alignment):.1f}, shown as {result.display_score}."
            )


def test_c_for_student_2_explains_why_it_is_not_ranked():
    exp = explain(score_section(STUDENT_2, SECTION_C))
    assert exp.headline.startswith("Not ranked: no single answer on following the plan.")
    assert "75% of your importance weight" in exp.headline and "53/100" in exp.headline
    assert len(exp.missing) == 1
    assert "following the plan" in exp.missing[0] and UNKNOWN_ANSWER_LABEL in exp.missing[0]
    assert "Never guessed" in exp.details[2]
    assert "counting only the questions this instructor answered" in exp.calculation


def test_tradeoffs_are_ordered_by_points_lost_not_by_gap():
    # discussion: 2 steps apart, very important -> loses 3 * 0.5  = 1.50 points
    # plan:       3 steps apart, slightly important -> loses 1 * 0.25 = 0.75 points
    student = StudentPreferences.from_lists([1, None, 5, None, None, None], [3, 0, 1, 0, 0, 0])
    section = SectionProfile.from_lists("S-01", "PM101", "Instructor S (fictional)",
                                        [3, 3, 2, 3, 3, 3], "synthetic fixture", True)
    exp = explain(score_section(student, section))
    assert exp.tradeoffs[0].startswith("Tradeoff on class discussion") and "2 steps apart" in exp.tradeoffs[0]
    assert exp.tradeoffs[1].startswith("Tradeoff on following the plan") and "3 steps apart" in exp.tradeoffs[1]


def test_one_step_is_singular_and_fractional_gaps_are_shown():
    student = StudentPreferences.from_lists([5, None, None, None, None, None], [1, 0, 0, 0, 0, 0])
    one = SectionProfile.from_lists("S-01", "PM101", "I (fictional)", [4, 1, 1, 1, 1, 1], "synthetic", True)
    half = SectionProfile.from_lists("S-02", "PM101", "J (fictional)", [4.5, 1, 1, 1, 1, 1], "synthetic", True)
    assert "(1 step apart)" in explain(score_section(student, one)).reasons[0]
    assert "(0.5 steps apart)" in explain(score_section(student, half)).reasons[0]


def test_insufficient_evidence_explanation():
    empty = SectionProfile.from_lists("PM101-09", "PM101", "Instructor Z (fictional)",
                                      [None] * 6, "synthetic fixture", True)
    exp = explain(score_section(STUDENT_1, empty))
    assert exp.headline.startswith("No score")
    assert exp.reasons == () and exp.tradeoffs == ()
    assert len(exp.missing) == 5  # Student 1 rated five questions
    assert exp.calculation is None


def test_no_preferences_explanation_is_descriptive_only():
    nothing = StudentPreferences.from_lists([None] * 6, [0] * 6)
    exp = explain(score_section(nothing, SECTION_B))
    assert exp.headline.startswith("No score")
    assert exp.reasons == () and exp.tradeoffs == () and exp.missing == ()
    assert all("no preference, so not used" in line for line in exp.details)


def test_explanations_are_deterministic():
    for prefs in DEMO_STUDENTS.values():
        for profile in PM101_SECTIONS:
            assert explain(score_section(prefs, profile)) == explain(score_section(prefs, profile))


def test_required_caveats_are_present():
    exp = explain(score_section(STUDENT_1, SECTION_B))
    assert NOT_A_PREDICTION in exp.caveats
    assert any(c.startswith("SYNTHETIC") for c in exp.caveats)
    assert any(c.startswith("Instructor answers:") for c in exp.caveats)


@pytest.mark.parametrize("word", ["probability", "success", "proven", "best", "worst", "guarantee"])
def test_explanations_avoid_forbidden_claims(word):
    # Section F: say "alignment score", never "probability of success" or rankings of professors.
    for result in every_result():
        assert word not in all_text(explain(result)).lower()


# --------------------------------------------------------------------------- command-line demo

def test_demo_runs_and_prints_the_worked_numbers(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC DEMO" in out
    for expected in ["90.909", "89.583", "52.778", "Eligible to rank", "no (partial)", "Questionnaire v2"]:
        assert expected in out


def test_demo_accepts_custom_preferences(capsys):
    assert main(["--prefs", "5,3,-,4,1,4", "--weights", "3,1,0,2,3,2"]) == 0
    assert "Custom student" in capsys.readouterr().out


def test_demo_reports_invalid_input_cleanly(capsys):
    assert main(["--prefs", "5,9,-,4,1,4", "--weights", "3,1,0,2,3,2"]) == 2
    assert "practice: preference must be a whole number" in capsys.readouterr().err
