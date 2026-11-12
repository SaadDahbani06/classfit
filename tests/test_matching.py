"""Scorer and ranking tests (roadmap section X, 'Core scorer'), questionnaire v2."""

from __future__ import annotations

import random
from fractions import Fraction

import pytest

from profmatch.matching import (
    COMPLETE,
    INSUFFICIENT_EVIDENCE,
    METHOD_VERSION,
    MISSING,
    MODE_NO_PREFERENCES,
    MODE_NO_SECTIONS,
    MODE_RANKED,
    MODE_SINGLE_OPTION,
    MODE_UNRANKED_INCOMPLETE,
    NO_PREFERENCES,
    NOT_REQUESTED,
    PARTIAL,
    SCORED,
    compare_sections,
    round_half_up,
    score_section,
    similarity,
)
from profmatch.models import SectionProfile, StudentPreferences
from profmatch.scale import DIMENSIONS, QUESTIONNAIRE_VERSION
from profmatch.synthetic import (
    PM101_SECTIONS,
    SECTION_A,
    SECTION_B,
    SECTION_C,
    STUDENT_1,
    STUDENT_2,
    SYNTHETIC_SOURCE,
)
from profmatch.validation import ValidationError


def make_profile(section_id, values, course="PM101", synthetic=True):
    return SectionProfile.from_lists(
        section_id, course, f"Instructor {section_id}", values,
        SYNTHETIC_SOURCE if synthetic else "test source", synthetic,
    )


def prefs(values, weights):
    return StudentPreferences.from_lists(values, weights)


def only(dimension, value, default=None):
    """A six-value list (DIMENSIONS order) with one dimension set."""
    return [value if d == dimension else default for d in DIMENSIONS]


def ranked_ids(comparison):
    return [e.result.section_id for e in comparison.ranked]


def ranks(comparison):
    return [e.rank for e in comparison.ranked]


# --------------------------------------------------------------------------- building blocks

@pytest.mark.parametrize(
    "p, x, expected",
    [
        (3, 3, Fraction(1)),
        (1, 5, Fraction(0)),
        (5, 1, Fraction(0)),
        (2, 4, Fraction(1, 2)),
        (5, 4, Fraction(3, 4)),
        (5, 3.5, Fraction(5, 8)),  # profile values may one day be medians, which can be halves
    ],
)
def test_similarity(p, x, expected):
    assert similarity(p, x) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (Fraction(1000, 11), 91),  # 90.909...
        (Fraction(1075, 12), 90),  # 89.583...
        (Fraction(475, 9), 53),    # 52.777...
        (Fraction(125, 2), 63),    # 62.5: built-in round() would give 62 (banker's rounding)
        (Fraction(127, 2), 64),    # 63.5
        (Fraction(0), 0),
        (Fraction(100), 100),
    ],
)
def test_round_half_up(value, expected):
    assert round_half_up(value) == expected


def test_score_equals_the_published_baseline_formula():
    # alignment = 100 x [1 - sum(w * |p - x|) / (4 * sum(w))], over questions both sides answered
    for student in (STUDENT_1, STUDENT_2):
        for section in PM101_SECTIONS:
            r = score_section(student, section)
            known = [d for d in r.dimensions if d.status == SCORED]
            gap = sum(d.weight * abs(Fraction(d.preference) - Fraction(d.observed)) for d in known)
            assert r.alignment == 100 * (1 - gap / (4 * sum(d.weight for d in known)))


# --------------------------------------------------------------------------- worked fixtures

def test_worked_fixture_student_1_and_b():
    r = score_section(STUDENT_1, SECTION_B)
    assert [d.similarity for d in r.dimensions] == [1, Fraction(1, 2), None, 1, 1, Fraction(3, 4)]
    assert r.dimensions[2].status == NOT_REQUESTED  # Student 1 has no preference on the plan
    assert sum(d.contribution for d in r.dimensions if d.status == SCORED) == 10
    assert r.alignment == Fraction(1000, 11)
    assert r.display_score == 91
    assert r.coverage == 1
    assert r.status == COMPLETE and r.eligible_for_ranking


def test_worked_fixture_student_2_and_a():
    r = score_section(STUDENT_2, SECTION_A)
    assert [d.similarity for d in r.dimensions] == [Fraction(1, 2), 1, 1, Fraction(3, 4), 1, Fraction(3, 4)]
    assert sum(d.contribution for d in r.dimensions) == Fraction(43, 4)
    assert r.alignment == Fraction(1075, 12)
    assert r.display_score == 90


def test_worked_fixture_c_is_partial_for_student_2():
    r = score_section(STUDENT_2, SECTION_C)
    assert r.total_weight == 12
    assert r.known_weight == 9
    assert r.coverage == Fraction(3, 4)
    assert r.alignment == Fraction(475, 9)
    assert r.display_score == 53
    assert r.status == PARTIAL
    assert not r.eligible_for_ranking
    assert r.missing_dimensions == ("plan",)


def test_c_is_complete_for_student_1_who_did_not_rate_the_plan():
    r = score_section(STUDENT_1, SECTION_C)
    assert r.status == COMPLETE
    assert r.alignment == Fraction(950, 11)  # 86.36
    assert r.dimensions[2].status == NOT_REQUESTED


def test_student_1_ranking():
    c = compare_sections(STUDENT_1, PM101_SECTIONS)
    assert c.mode == MODE_RANKED
    assert ranked_ids(c) == ["PM101-02", "PM101-03", "PM101-05", "PM101-04", "PM101-01"]
    assert [e.result.display_score for e in c.ranked] == [91, 86, 70, 64, 45]
    assert ranks(c) == [1, 2, 3, 4, 5]
    assert c.needs_more_info == ()


def test_student_2_ranking():
    c = compare_sections(STUDENT_2, PM101_SECTIONS)
    assert ranked_ids(c) == ["PM101-01", "PM101-05", "PM101-04", "PM101-02"]
    assert [e.result.display_score for e in c.ranked] == [90, 75, 65, 23]
    assert [r.section_id for r in c.needs_more_info] == ["PM101-03"]


def test_the_two_demo_students_get_opposite_closest_matches():
    first, second = compare_sections(STUDENT_1, PM101_SECTIONS), compare_sections(STUDENT_2, PM101_SECTIONS)
    assert ranked_ids(first)[0] == ranked_ids(second)[-1] == "PM101-02"   # B: closest for 1, furthest for 2
    assert ranked_ids(second)[0] == ranked_ids(first)[-1] == "PM101-01"   # A: closest for 2, furthest for 1


def test_incomplete_section_cannot_outrank_complete_ones_even_with_a_higher_partial_score():
    # Matches Student 2 on every question it answered, but gave no answer on the plan.
    twin = make_profile("PM101-06", [2, 5, None, 3, 4, 2])
    c = compare_sections(STUDENT_2, [*PM101_SECTIONS, twin])
    partial = next(r for r in c.needs_more_info if r.section_id == "PM101-06")
    assert partial.display_score == 100 > c.ranked[0].result.display_score  # 100 > 90 ...
    assert c.ranked[0].result.section_id == "PM101-01"                       # ... yet A is ranked first
    assert "PM101-06" not in ranked_ids(c)


# --------------------------------------------------------------------------- extremes

@pytest.mark.parametrize(
    "values, weights",
    [
        ([1] * 6, [1] * 6),
        ([5] * 6, [3] * 6),
        ([2, 3, 4, 5, 1, 2], [3, 0, 2, 1, 1, 3]),
        ([3, None, 3, 3, None, 3], [1, 0, 2, 3, 0, 1]),
    ],
)
def test_exact_match_scores_100(values, weights):
    student = prefs(values, weights)
    section = make_profile("S-01", [v if v is not None else 3 for v in values])
    r = score_section(student, section)
    assert r.alignment == 100
    assert r.display_score == 100


@pytest.mark.parametrize(
    "values, section_values",
    [
        ([1, 1, 5, 5, 1, 5], [5, 5, 1, 1, 5, 1]),
        ([5] * 6, [1] * 6),
    ],
)
def test_maximally_opposite_scores_0(values, section_values):
    r = score_section(prefs(values, [3, 2, 1, 1, 2, 3]), make_profile("S-01", section_values))
    assert r.alignment == 0
    assert r.display_score == 0
    assert r.status == COMPLETE  # a 0 is a real, fully evidenced score, not missing data


# --------------------------------------------------------------------------- weights and ignored preferences

def test_zero_weight_removes_a_questions_effect():
    student = prefs([5, 3, 2, 4, 1, 4], [3, 0, 0, 2, 3, 2])  # practice and plan answered but weight 0
    a1 = make_profile("S-01", [4, 1, 5, 4, 1, 4])
    a2 = make_profile("S-02", [4, 5, 1, 4, 1, 4])  # differs only on the two weight-0 questions
    r1, r2 = score_section(student, a1), score_section(student, a2)
    assert r1.alignment == r2.alignment == Fraction(185, 2)  # (3*0.75 + 2 + 3 + 2) / 10
    assert r1.dimensions[1].status == NOT_REQUESTED


def test_no_preference_questions_never_affect_any_score():
    # Student 1 has no preference on the plan, so changing every instructor's plan answer changes nothing.
    changed = [
        make_profile(s.section_id, [s.values[d] if d != "plan" else plan for d in DIMENSIONS])
        for s, plan in zip(PM101_SECTIONS, [1, 5, 2, None, 4])
    ]
    before = [r.alignment for r in compare_sections(STUDENT_1, PM101_SECTIONS).all_results]
    after = [r.alignment for r in compare_sections(STUDENT_1, changed).all_results]
    assert before == after


def test_importance_weights_change_the_order():
    p_match_discussion = make_profile("S-01", [5, 1, None, None, None, None])
    q_match_practice = make_profile("S-02", [1, 5, None, None, None, None])
    values = [5, 5, None, None, None, None]
    discussion_first = compare_sections(prefs(values, [3, 1, 0, 0, 0, 0]), [p_match_discussion, q_match_practice])
    practice_first = compare_sections(prefs(values, [1, 3, 0, 0, 0, 0]), [p_match_discussion, q_match_practice])
    assert ranked_ids(discussion_first) == ["S-01", "S-02"]
    assert ranked_ids(practice_first) == ["S-02", "S-01"]


def test_zero_weight_on_the_missing_question_makes_c_complete():
    # Student 2, but with no preference on the plan: C's missing answer no longer matters.
    student = prefs([2, 5, None, 3, 4, 2], [1, 3, 0, 1, 2, 2])
    c = compare_sections(student, PM101_SECTIONS)
    assert c.mode == MODE_RANKED
    assert c.needs_more_info == ()
    assert "PM101-03" in ranked_ids(c)


@pytest.mark.parametrize(
    "values",
    [[None] * 6, [5, 3, 2, 4, 1, 4]],  # unanswered, or answered but nothing marked important
)
def test_all_zero_weights_give_no_scores_and_no_ranking(values):
    c = compare_sections(prefs(values, [0] * 6), PM101_SECTIONS)
    assert c.mode == MODE_NO_PREFERENCES
    assert c.ranked == ()
    assert [r.section_id for r in c.all_results] == ["PM101-01", "PM101-02", "PM101-03", "PM101-04", "PM101-05"]
    for r in c.all_results:
        assert r.alignment is None and r.display_score is None and r.coverage is None
        assert r.status == NO_PREFERENCES
        assert not r.eligible_for_ranking


# --------------------------------------------------------------------------- missing instructor answers

@pytest.mark.parametrize("imputed", [1, 3, 5])
def test_unknown_is_never_treated_as_a_low_value_the_midpoint_or_a_match(imputed):
    actual = score_section(STUDENT_2, SECTION_C)
    as_if_imputed = score_section(
        STUDENT_2, make_profile("PM101-03", [SECTION_C.values[d] if d != "plan" else imputed for d in DIMENSIONS])
    )
    assert actual.alignment != as_if_imputed.alignment
    assert actual.dimensions[2].status == MISSING
    assert actual.dimensions[2].similarity is None
    assert actual.dimensions[2].contribution is None


def test_no_usable_evidence_gives_insufficient_evidence_not_a_score():
    empty = make_profile("PM101-09", [None] * 6)
    r = score_section(STUDENT_1, empty)
    assert r.status == INSUFFICIENT_EVIDENCE
    assert r.alignment is None and r.display_score is None
    assert r.coverage == 0
    assert not r.eligible_for_ranking


def test_no_complete_profiles_gives_unranked_comparison_listing_missing_questions():
    empty = make_profile("PM101-09", [None] * 6)
    c = compare_sections(STUDENT_2, [empty, SECTION_C])
    assert c.mode == MODE_UNRANKED_INCOMPLETE
    assert c.ranked == ()
    assert [r.section_id for r in c.needs_more_info] == ["PM101-03", "PM101-09"]  # by ID, not score
    assert c.needs_more_info[0].missing_dimensions == ("plan",)
    assert c.needs_more_info[1].missing_dimensions == DIMENSIONS  # Student 2 rated all six


def test_single_complete_section_is_not_presented_as_a_ranking():
    c = compare_sections(STUDENT_2, [SECTION_A, SECTION_C])
    assert c.mode == MODE_SINGLE_OPTION
    assert ranked_ids(c) == ["PM101-01"]
    assert [r.section_id for r in c.needs_more_info] == ["PM101-03"]


def test_no_sections():
    c = compare_sections(STUDENT_1, [])
    assert c.mode == MODE_NO_SECTIONS
    assert c.all_results == ()


# --------------------------------------------------------------------------- ties and determinism

def test_equal_displayed_scores_share_rank_and_sort_by_section_id():
    student = prefs(only("discussion", 5), only("discussion", 1, default=0))
    sections = [
        make_profile("S-04", only("discussion", 3)),     # 50
        make_profile("S-02", only("discussion", 4.97)),  # 99.25 -> 99
        make_profile("S-03", only("discussion", 5)),     # 100
        make_profile("S-01", only("discussion", 4.96)),  # 99.00 -> 99
    ]
    c = compare_sections(student, sections)
    # S-02 has the higher exact score, but S-01 and S-02 display the same 99,
    # so they share rank 2 and are listed by ID. Tiny decimals never pick a winner.
    assert ranked_ids(c) == ["S-03", "S-01", "S-02", "S-04"]
    assert ranks(c) == [1, 2, 2, 4]
    s01, s02 = c.ranked[1].result, c.ranked[2].result
    assert s02.alignment > s01.alignment


def test_tie_for_first_uses_competition_ranking():
    student = prefs(only("exams", 2), only("exams", 1, default=0))
    sections = [make_profile("S-01", only("exams", 2)), make_profile("S-02", only("exams", 2)),
                make_profile("S-03", only("exams", 4))]
    c = compare_sections(student, sections)
    assert ranks(c) == [1, 1, 3]  # the next rank after a two-way tie is 3


def test_results_do_not_depend_on_input_order():
    extra = [make_profile("PM101-06", [3] * 6), make_profile("PM101-07", [None, 2, 2, None, 4, 4])]
    sections = list(PM101_SECTIONS) + extra
    baseline = compare_sections(STUDENT_1, sections)
    rng = random.Random(20261014)
    for _ in range(25):
        shuffled = sections[:]
        rng.shuffle(shuffled)
        assert compare_sections(STUDENT_1, shuffled) == baseline


def test_method_and_questionnaire_versions_are_recorded():
    c = compare_sections(STUDENT_1, PM101_SECTIONS)
    assert c.method_version == METHOD_VERSION
    assert c.questionnaire_version == QUESTIONNAIRE_VERSION == "v2"


# --------------------------------------------------------------------------- comparability guards

def test_duplicate_section_ids_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate section ID"):
        compare_sections(STUDENT_1, [SECTION_A, SECTION_A])


def test_sections_from_different_courses_are_not_pooled():
    other = make_profile("PM202-01", [4, 5, 5, 2, 4, 1], course="PM202")
    with pytest.raises(ValidationError, match="different courses"):
        compare_sections(STUDENT_1, [SECTION_A, other])


def test_synthetic_and_real_profiles_cannot_be_mixed():
    real = make_profile("PM101-07", [4, 5, 5, 2, 4, 1], synthetic=False)
    with pytest.raises(ValidationError, match="Synthetic and real"):
        compare_sections(STUDENT_1, [SECTION_A, real])


def test_non_profile_input_is_rejected():
    with pytest.raises(ValidationError, match="Expected SectionProfile"):
        compare_sections(STUDENT_1, [{"section_id": "X"}])
