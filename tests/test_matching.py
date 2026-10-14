"""Scorer and ranking tests (roadmap section X, 'Core scorer')."""

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
    compare_sections,
    round_half_up,
    score_section,
    similarity,
)
from profmatch.models import SectionProfile, StudentPreferences
from profmatch.scale import DIMENSIONS
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
        (5, 3.5, Fraction(5, 8)),  # profile medians can be halves
    ],
)
def test_similarity(p, x, expected):
    assert similarity(p, x) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (Fraction(800, 9), 89),   # 88.888...
        (Fraction(250, 9), 28),   # 27.777...
        (Fraction(575, 6), 96),   # 95.833...
        (Fraction(125, 2), 63),   # 62.5: built-in round() would give 62 (banker's rounding)
        (Fraction(127, 2), 64),   # 63.5
        (Fraction(0), 0),
        (Fraction(100), 100),
    ],
)
def test_round_half_up(value, expected):
    assert round_half_up(value) == expected


# --------------------------------------------------------------------------- section H worked fixture

def test_worked_fixture_a():
    r = score_section(STUDENT_1, SECTION_A)
    assert [d.similarity for d in r.dimensions] == [1, Fraction(3, 4), 1, Fraction(3, 4)]
    assert sum(d.contribution for d in r.dimensions) == 8
    assert r.alignment == Fraction(800, 9)
    assert r.display_score == 89
    assert r.coverage == 1
    assert r.status == COMPLETE and r.eligible_for_ranking


def test_worked_fixture_b():
    r = score_section(STUDENT_1, SECTION_B)
    assert [d.similarity for d in r.dimensions] == [Fraction(1, 4)] * 3 + [Fraction(1, 2)]
    assert sum(d.contribution for d in r.dimensions) == Fraction(5, 2)
    assert r.alignment == Fraction(250, 9)
    assert r.display_score == 28
    assert r.status == COMPLETE


def test_worked_fixture_c_partial():
    r = score_section(STUDENT_1, SECTION_C)
    assert r.total_weight == 9
    assert r.known_weight == 6
    assert r.coverage == Fraction(2, 3)
    assert r.alignment == Fraction(575, 6)
    assert r.display_score == 96
    assert r.status == PARTIAL
    assert not r.eligible_for_ranking
    assert r.missing_dimensions == ("assessment",)


def test_student_1_ranking_matches_worked_example():
    c = compare_sections(STUDENT_1, PM101_SECTIONS)
    assert c.mode == MODE_RANKED
    assert ranked_ids(c) == ["PM101-01", "PM101-02"]
    assert ranks(c) == [1, 2]
    assert [r.section_id for r in c.needs_more_info] == ["PM101-03"]


def test_incomplete_c_cannot_outrank_complete_a():
    c = compare_sections(STUDENT_1, PM101_SECTIONS)
    c_result = next(r for r in c.all_results if r.section_id == "PM101-03")
    a_entry = next(e for e in c.ranked if e.result.section_id == "PM101-01")
    assert c_result.display_score > a_entry.result.display_score  # 96 > 89 ...
    assert a_entry.rank == 1                                      # ... yet A is ranked first
    assert "PM101-03" not in ranked_ids(c)                         # and C is not ranked at all


def test_student_2_gets_b_as_top_complete_match_at_100():
    c = compare_sections(STUDENT_2, PM101_SECTIONS)
    top = c.ranked[0]
    assert top.result.section_id == "PM101-02"
    assert top.result.alignment == 100
    assert top.rank == 1


def test_reversed_preferences_reverse_the_ranking():
    assert ranked_ids(compare_sections(STUDENT_1, PM101_SECTIONS)) == ["PM101-01", "PM101-02"]
    assert ranked_ids(compare_sections(STUDENT_2, PM101_SECTIONS)) == ["PM101-02", "PM101-01"]


# --------------------------------------------------------------------------- extremes

@pytest.mark.parametrize(
    "values, weights",
    [
        ([1, 1, 1, 1], [1, 1, 1, 1]),
        ([5, 5, 5, 5], [3, 3, 3, 3]),
        ([2, 3, 4, 5], [3, 0, 2, 1]),
        ([3, None, 3, 3], [1, 0, 2, 3]),
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
        ([1, 1, 5, 5], [5, 5, 1, 1]),
        ([5, 5, 5, 5], [1, 1, 1, 1]),
    ],
)
def test_maximally_opposite_scores_0(values, section_values):
    r = score_section(prefs(values, [3, 2, 1, 1]), make_profile("S-01", section_values))
    assert r.alignment == 0
    assert r.display_score == 0
    assert r.status == COMPLETE  # a 0 is a real, fully evidenced score, not missing data


# --------------------------------------------------------------------------- weights

def test_zero_weight_removes_a_dimensions_effect():
    student = prefs([2, 5, 1, 4], [3, 0, 2, 1])
    a1 = make_profile("S-01", [2, 1, 1, 5])
    a2 = make_profile("S-02", [2, 5, 1, 5])  # differs only on assessment, which has weight 0
    r1, r2 = score_section(student, a1), score_section(student, a2)
    assert r1.alignment == r2.alignment == Fraction(575, 6)  # (3*1 + 2*1 + 1*0.75) / 6
    assert r1.dimensions[1].status == NOT_REQUESTED


def test_zero_weight_on_missing_dimension_makes_c_complete_and_ties_with_a():
    # Student 1, but assessment no longer matters. C's missing value is now irrelevant.
    student = prefs([2, None, 1, 4], [3, 0, 2, 1])
    c = compare_sections(student, PM101_SECTIONS)
    assert c.mode == MODE_RANKED
    assert c.needs_more_info == ()
    # A and C now have identical evidence on every rated dimension: tie at 96.
    assert ranked_ids(c) == ["PM101-01", "PM101-03", "PM101-02"]
    assert ranks(c) == [1, 1, 3]  # competition ranking: the next rank after a 2-way tie is 3


@pytest.mark.parametrize(
    "values",
    [[None, None, None, None], [2, 5, 1, 4]],  # unanswered, or answered but nothing marked important
)
def test_all_zero_weights_give_no_scores_and_no_ranking(values):
    c = compare_sections(prefs(values, [0, 0, 0, 0]), PM101_SECTIONS)
    assert c.mode == MODE_NO_PREFERENCES
    assert c.ranked == ()
    assert [r.section_id for r in c.all_results] == ["PM101-01", "PM101-02", "PM101-03"]
    for r in c.all_results:
        assert r.alignment is None and r.display_score is None and r.coverage is None
        assert r.status == NO_PREFERENCES
        assert not r.eligible_for_ranking


# --------------------------------------------------------------------------- missing data

@pytest.mark.parametrize("imputed", [1, 3])
def test_null_is_never_treated_as_a_low_value_or_the_midpoint(imputed):
    actual = score_section(STUDENT_1, SECTION_C)
    imputed_values = dict(SECTION_C.values, assessment=imputed)
    as_if_imputed = score_section(
        STUDENT_1, make_profile("PM101-03", [imputed_values[d] for d in imputed_values])
    )
    assert actual.alignment != as_if_imputed.alignment
    assert actual.dimensions[1].status == MISSING
    assert actual.dimensions[1].similarity is None
    assert actual.dimensions[1].contribution is None


def test_no_usable_evidence_gives_insufficient_evidence_not_a_score():
    empty = make_profile("PM101-09", [None, None, None, None])
    r = score_section(STUDENT_1, empty)
    assert r.status == INSUFFICIENT_EVIDENCE
    assert r.alignment is None and r.display_score is None
    assert r.coverage == 0
    assert not r.eligible_for_ranking


def test_no_complete_profiles_gives_unranked_comparison_listing_missing_dimensions():
    empty = make_profile("PM101-09", [None, None, None, None])
    c = compare_sections(STUDENT_1, [empty, SECTION_C])
    assert c.mode == MODE_UNRANKED_INCOMPLETE
    assert c.ranked == ()
    assert [r.section_id for r in c.needs_more_info] == ["PM101-03", "PM101-09"]  # by ID, not score
    assert c.needs_more_info[0].missing_dimensions == ("assessment",)
    assert c.needs_more_info[1].missing_dimensions == DIMENSIONS


def test_single_complete_section_is_not_presented_as_a_ranking():
    c = compare_sections(STUDENT_1, [SECTION_A, SECTION_C])
    assert c.mode == MODE_SINGLE_OPTION
    assert ranked_ids(c) == ["PM101-01"]


def test_no_sections():
    c = compare_sections(STUDENT_1, [])
    assert c.mode == MODE_NO_SECTIONS
    assert c.all_results == ()


# --------------------------------------------------------------------------- ties and determinism

def test_equal_displayed_scores_share_rank_and_sort_by_section_id():
    student = prefs([5, None, None, None], [1, 0, 0, 0])
    sections = [
        make_profile("S-04", [3, None, None, None]),     # 50
        make_profile("S-02", [4.97, None, None, None]),  # 99.25 -> 99
        make_profile("S-03", [5, None, None, None]),     # 100
        make_profile("S-01", [4.96, None, None, None]),  # 99.00 -> 99
    ]
    c = compare_sections(student, sections)
    # S-02 has the higher exact score, but S-01 and S-02 display the same 99,
    # so they share rank 2 and are listed by ID. Tiny decimals never pick a winner.
    assert ranked_ids(c) == ["S-03", "S-01", "S-02", "S-04"]
    assert ranks(c) == [1, 2, 2, 4]
    s01, s02 = c.ranked[1].result, c.ranked[2].result
    assert s02.alignment > s01.alignment


def test_results_do_not_depend_on_input_order():
    extra = [make_profile("PM101-04", [3, 3, 3, 3]), make_profile("PM101-05", [None, 2, 2, None])]
    sections = list(PM101_SECTIONS) + extra
    baseline = compare_sections(STUDENT_1, sections)
    rng = random.Random(20261014)
    for _ in range(25):
        shuffled = sections[:]
        rng.shuffle(shuffled)
        assert compare_sections(STUDENT_1, shuffled) == baseline


def test_method_version_is_recorded():
    assert compare_sections(STUDENT_1, PM101_SECTIONS).method_version == METHOD_VERSION


# --------------------------------------------------------------------------- comparability guards

def test_duplicate_section_ids_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate section ID"):
        compare_sections(STUDENT_1, [SECTION_A, SECTION_A])


def test_sections_from_different_courses_are_not_pooled():
    other = make_profile("PM202-01", [2, 4, 1, 5], course="PM202")
    with pytest.raises(ValidationError, match="different courses"):
        compare_sections(STUDENT_1, [SECTION_A, other])


def test_synthetic_and_real_profiles_cannot_be_mixed():
    real = make_profile("PM101-07", [2, 4, 1, 5], synthetic=False)
    with pytest.raises(ValidationError, match="Synthetic and real"):
        compare_sections(STUDENT_1, [SECTION_A, real])


def test_non_profile_input_is_rejected():
    with pytest.raises(ValidationError, match="Expected SectionProfile"):
        compare_sections(STUDENT_1, [{"section_id": "X"}])
