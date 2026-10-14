"""Importer tests: form exports -> validated professor profiles, with an audit of every skipped row."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from profmatch.forms import (
    FormImportError,
    course_display,
    course_key,
    group_by_course,
    group_label,
    load_professor_responses,
    parse_scale_answer,
)
from profmatch.matching import compare_sections
from profmatch.synthetic import STUDENT_1
from profmatch.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DEMO_FILE = ROOT / "data" / "demo" / "professor_responses_demo.csv"
TEMPLATE_FILE = ROOT / "data" / "templates" / "professor_responses_template.csv"

GOOGLE_HEADER = [
    "Timestamp",
    "Q1. Your name as you'd like students to see it",
    "Q2. Course code",
    "Q3. Term",
    "Q4. Section number(s)",
    "Q5. Class time",
    "Q6. Graded work",
    "Q7. Individual or group",
    "Q8. Advance structure",
    "Q9. Note",
    "Q10. Consent",
]
YES = "Yes, show my name and answers"


def write_csv(tmp_path, header, rows, name="responses.csv", encoding="utf-8"):
    path = tmp_path / name
    with open(path, "w", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def response(name="Dr. Test", course="MATH 130", term="Spring 2027", answers=("2", "4", "1", "5"),
             consent=YES, sections="111", note=""):
    return ["10/14/2026 10:00:00", name, course, term, sections, *answers, note, consent]


# --------------------------------------------------------------------------- parsing answers

@pytest.mark.parametrize(
    "cell, expected",
    [
        ("3", 3),
        ("1 — Mostly lecture", 1),
        ("5 - Mostly group work", 5),
        ("2: between", 2),
        ("4 Between mixed and mostly group work", 4),
        ("Not sure / it varies", None),
        ("not sure", None),
        ("", None),
        ("   ", None),
    ],
)
def test_parse_scale_answer(cell, expected):
    assert parse_scale_answer("format", cell) == expected


@pytest.mark.parametrize("cell", ["0", "6", "35", "3.5", "three", "Mostly lecture", "-3"])
def test_parse_scale_answer_rejects_unreadable_answers(cell):
    with pytest.raises(ValidationError, match="format: could not read"):
        parse_scale_answer("format", cell)


@pytest.mark.parametrize("raw, key, shown", [
    ("MATH 130", "MATH130", "MATH 130"),
    ("math130", "MATH130", "MATH 130"),
    ("Math-130", "MATH130", "MATH 130"),
    ("CMPT 120L", "CMPT120L", "CMPT 120L"),
])
def test_course_codes_are_normalized(raw, key, shown):
    assert course_key(raw) == key
    assert course_display(course_key(raw)) == shown


# --------------------------------------------------------------------------- demo file

def test_demo_file_loads_with_expected_audit():
    result = load_professor_responses(DEMO_FILE, synthetic=True)
    audit = result.audit
    assert audit.rows_read == 9
    assert audit.loaded == 7
    assert audit.excluded == ((10, "no consent to display"),)
    assert audit.replaced == ((4, 8),)
    assert len(audit.file_sha256) == 64
    assert all(e.profile.is_synthetic for e in result.entries)


def test_demo_file_matches_the_engine_fixtures():
    result = load_professor_responses(DEMO_FILE, synthetic=True)
    by_name = {e.name: e.profile.values for e in result.entries}
    assert list(by_name["Instructor A (fictional)"].values()) == [2, 4, 1, 5]
    assert list(by_name["Instructor B (fictional)"].values()) == [5, 2, 4, 2]
    assert list(by_name["Instructor C (fictional)"].values()) == [2, None, 1, 5]
    assert list(by_name["Instructor E (fictional)"].values()) == [4, 5, 2, 4]  # the newer submission


def test_demo_courses_are_grouped_and_never_pooled():
    groups = group_by_course(load_professor_responses(DEMO_FILE, synthetic=True).entries)
    labels = [group_label(g) for g in groups.values()]
    assert labels == ["PM 101 · Spring 2027", "PM 102 · Spring 2027"]  # "PM 102" and "PM102" merged
    assert [len(g) for g in groups.values()] == [5, 2]


def test_demo_end_to_end_ranking_for_student_1():
    groups = group_by_course(load_professor_responses(DEMO_FILE, synthetic=True).entries)
    pm101 = next(iter(groups.values()))
    comparison = compare_sections(STUDENT_1, [e.profile for e in pm101])
    assert [(e.rank, e.result.profile.instructor, e.result.display_score) for e in comparison.ranked] == [
        (1, "Instructor A (fictional)", 89),
        (2, "Instructor E (fictional)", 78),
        (3, "Instructor D (fictional)", 61),
        (4, "Instructor B (fictional)", 28),
    ]
    assert [r.profile.instructor for r in comparison.needs_more_info] == ["Instructor C (fictional)"]


def test_template_has_the_same_columns_as_the_demo_file():
    with open(TEMPLATE_FILE, encoding="utf-8") as t, open(DEMO_FILE, encoding="utf-8") as d:
        assert next(csv.reader(t)) == next(csv.reader(d))


# --------------------------------------------------------------------------- row rules

def test_rows_without_consent_are_skipped_and_reported(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [
        response(name="Dr. Yes"),
        response(name="Dr. No", consent="No, do not show my responses"),
        response(name="Dr. Blank", consent=""),
    ])
    result = load_professor_responses(path, synthetic=False)
    assert [e.name for e in result.entries] == ["Dr. Yes"]
    assert result.audit.excluded == ((3, "no consent to display"), (4, "no consent to display"))


def test_skipped_reasons_never_contain_the_name_of_someone_who_declined(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(name="Dr. Private", consent="No")])
    audit = load_professor_responses(path, synthetic=False).audit
    assert "Private" not in str(audit)


def test_invalid_answer_excludes_the_row_with_a_reason(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(answers=("2", "7", "1", "5"))])
    result = load_professor_responses(path, synthetic=False)
    assert result.entries == ()
    (row, reason), = result.audit.excluded
    assert row == 2 and "assessment" in reason and "'7'" in reason


@pytest.mark.parametrize("field, kwargs", [
    ("name", {"name": "  "}),
    ("course code", {"course": "--"}),
    ("term", {"term": ""}),
])
def test_missing_required_values_exclude_the_row(tmp_path, field, kwargs):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(**kwargs)])
    (row, reason), = load_professor_responses(path, synthetic=False).audit.excluded
    assert reason == f"missing {field}"


def test_not_sure_becomes_unknown_never_a_number(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(answers=("2", "Not sure / it varies", "1", "5"))])
    (entry,) = load_professor_responses(path, synthetic=False).entries
    assert entry.profile.values["assessment"] is None


def test_resubmission_keeps_the_latest_and_reimport_is_stable(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [
        response(name="Dr. Twice", answers=("1", "1", "1", "1")),
        response(name="dr.  twice", course="math130", term="spring 2027", answers=("5", "5", "5", "5")),
    ])
    first = load_professor_responses(path, synthetic=False)
    assert len(first.entries) == 1
    assert list(first.entries[0].profile.values.values()) == [5, 5, 5, 5]
    assert first.audit.replaced == ((2, 3),)
    assert load_professor_responses(path, synthetic=False) == first  # same file -> identical result


def test_different_terms_are_kept_apart(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [
        response(name="Dr. Same", term="Fall 2026"),
        response(name="Dr. Same", term="Spring 2027"),
    ])
    groups = group_by_course(load_professor_responses(path, synthetic=False).entries)
    assert len(groups) == 2


def test_real_and_synthetic_labels_come_from_the_file_not_the_rows(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response()])
    real = load_professor_responses(path, synthetic=False)
    assert not real.entries[0].profile.is_synthetic
    assert real.entries[0].profile.source.startswith("self-reported by the instructor")


# --------------------------------------------------------------------------- file-level rules

def test_microsoft_forms_export_with_extra_columns_and_bom(tmp_path):
    header = ["ID", "Start time", "Completion time", "Email", "Name"] + GOOGLE_HEADER[1:]
    row = ["1", "x", "y", "prof@example.edu", "Anonymous"] + response()[1:]
    path = write_csv(tmp_path, header, [row], encoding="utf-8-sig")
    (entry,) = load_professor_responses(path, synthetic=False).entries
    assert entry.name == "Dr. Test"
    assert "example.edu" not in str(entry)  # email column is ignored, never stored


def test_reworded_questions_still_import_by_number(tmp_path):
    header = ["Timestamp"] + [h.split(".")[0] + ". Completely reworded" for h in GOOGLE_HEADER[1:]]
    path = write_csv(tmp_path, header, [response()])
    assert len(load_professor_responses(path, synthetic=False).entries) == 1


def test_missing_required_column_is_a_clear_file_error(tmp_path):
    header = [h for h in GOOGLE_HEADER if not h.startswith("Q6.")]
    path = write_csv(tmp_path, header, [])
    with pytest.raises(FormImportError, match=r"No column starts with 'Q6\.'"):
        load_professor_responses(path, synthetic=False)


def test_q1_prefix_does_not_match_q10(tmp_path):
    # "Q10." must not be mistaken for "Q1." (and vice versa).
    path = write_csv(tmp_path, GOOGLE_HEADER, [response()])
    (entry,) = load_professor_responses(path, synthetic=False).entries
    assert entry.name == "Dr. Test"


def test_duplicate_question_numbers_are_rejected(tmp_path):
    header = GOOGLE_HEADER + ["Q5. Asked twice"]
    path = write_csv(tmp_path, header, [])
    with pytest.raises(FormImportError, match="More than one column"):
        load_professor_responses(path, synthetic=False)


def test_empty_file_is_a_clear_error(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    with pytest.raises(FormImportError, match="empty"):
        load_professor_responses(path, synthetic=False)
