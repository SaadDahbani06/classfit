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
from profmatch.matching import MODE_SINGLE_OPTION, compare_sections
from profmatch.scale import QUESTIONS
from profmatch.synthetic import PM101_SECTIONS, STUDENT_1, STUDENT_2
from profmatch.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DEMO_FILE = ROOT / "data" / "demo" / "professor_responses_demo.csv"
TEMPLATE_FILE = ROOT / "data" / "templates" / "professor_responses_template.csv"

GOOGLE_HEADER = [
    "Timestamp",
    "Q1. Your name as students should see it",
    "Q2. Course code",
    "Q3. Term",
    "Q4. Section number(s)",
    "Q5. Class discussion — how often?",
    "Q6. Guided practice — how much class time?",
    "Q7. Following the plan — how closely?",
    "Q8. Concepts and applications — what balance?",
    "Q9. Timed quizzes and exams — what share of the grade?",
    "Q10. Collaborative graded work — what share of the grade?",
    "Q11. Note",
    "Q12. Consent",
]
VERSION_1_HEADER = [
    "Timestamp", "Q1. Your name", "Q2. Course code", "Q3. Term", "Q4. Section number(s)",
    "Q5. In this course, how is class time mostly spent?", "Q6. How is graded work distributed?",
    "Q7. Are assessed assignments mostly individual or group work?",
    "Q8. How much of the course plan is fixed in advance?", "Q9. Anything students should know?",
    "Q10. May Prof-Match show your name and these answers to students in the pilot?",
]
YES = "Yes, show my name and answers"


def write_csv(tmp_path, header, rows, name="responses.csv", encoding="utf-8"):
    path = tmp_path / name
    with open(path, "w", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def response(name="Dr. Test", course="MATH 130", term="Spring 2027", answers=("4", "5", "5", "2", "4", "1"),
             consent=YES, sections="111", note=""):
    return ["10/14/2026 10:00:00", name, course, term, sections, *answers, note, consent]


# --------------------------------------------------------------------------- parsing answers

@pytest.mark.parametrize(
    "cell, expected",
    [
        ("3", 3),
        ("1 — Rarely (0–20% of class sessions)", 1),
        ("5 - 81–100% of the course grade", 5),
        ("2: Some", 2),
        ("4 Most", 4),
        ("Varies / unable to answer", None),
        ("varies", None),
        ("Unable to answer", None),
        ("", None),
        ("   ", None),
    ],
)
def test_parse_scale_answer(cell, expected):
    assert parse_scale_answer("discussion", cell) == expected


@pytest.mark.parametrize("cell", [
    "0", "6", "35", "3.5", "three", "Often", "-3",
    "Not sure / it varies",          # version 1's label is not silently treated as version 2's
    "21–40% of the course grade",    # a range without its option number is not read as 2
])
def test_parse_scale_answer_rejects_unreadable_answers(cell):
    with pytest.raises(ValidationError, match="discussion: could not read"):
        parse_scale_answer("discussion", cell)


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
    for section in PM101_SECTIONS:  # includes Instructor E's newer submission
        assert by_name[section.instructor] == section.values


def test_demo_courses_are_grouped_and_never_pooled():
    groups = group_by_course(load_professor_responses(DEMO_FILE, synthetic=True).entries)
    labels = [group_label(g) for g in groups.values()]
    assert labels == ["PM 101 · Spring 2027", "PM 102 · Spring 2027"]  # "PM 102" and "PM102" merged
    assert [len(g) for g in groups.values()] == [5, 2]


def test_demo_end_to_end_for_both_students():
    pm101 = next(iter(group_by_course(load_professor_responses(DEMO_FILE, synthetic=True).entries).values()))
    profiles = [e.profile for e in pm101]
    first, second = compare_sections(STUDENT_1, profiles), compare_sections(STUDENT_2, profiles)
    assert [(e.rank, e.result.profile.instructor, e.result.display_score) for e in first.ranked] == [
        (1, "Instructor B (fictional)", 91),
        (2, "Instructor C (fictional)", 86),
        (3, "Instructor E (fictional)", 70),
        (4, "Instructor D (fictional)", 64),
        (5, "Instructor A (fictional)", 45),
    ]
    assert [(e.rank, e.result.profile.instructor, e.result.display_score) for e in second.ranked] == [
        (1, "Instructor A (fictional)", 90),
        (2, "Instructor E (fictional)", 75),
        (3, "Instructor D (fictional)", 65),
        (4, "Instructor B (fictional)", 23),
    ]
    assert [r.profile.instructor for r in second.needs_more_info] == ["Instructor C (fictional)"]


def test_second_demo_course_has_a_single_complete_option():
    pm102 = list(group_by_course(load_professor_responses(DEMO_FILE, synthetic=True).entries).values())[1]
    for student in (STUDENT_1, STUDENT_2):
        comparison = compare_sections(student, [e.profile for e in pm102])
        assert comparison.mode == MODE_SINGLE_OPTION
        assert comparison.ranked[0].result.profile.instructor == "Instructor F (fictional)"


def test_template_has_the_same_columns_as_the_demo_file():
    with open(TEMPLATE_FILE, encoding="utf-8") as t, open(DEMO_FILE, encoding="utf-8") as d:
        assert next(csv.reader(t)) == next(csv.reader(d))


def test_template_titles_carry_each_questions_number_and_topic():
    with open(TEMPLATE_FILE, encoding="utf-8") as t:
        header = next(csv.reader(t))
    for number, q in enumerate(QUESTIONS, start=5):
        assert header[number].startswith(f"Q{number}. {q.topic} — {q.instructor_question}")


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
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(answers=("4", "7", "5", "2", "4", "1"))])
    result = load_professor_responses(path, synthetic=False)
    assert result.entries == ()
    (row, reason), = result.audit.excluded
    assert row == 2 and "practice" in reason and "'7'" in reason


def test_version_1_unknown_label_is_rejected_not_mapped(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(answers=("4", "5", "Not sure / it varies", "2", "4", "1"))])
    (row, reason), = load_professor_responses(path, synthetic=False).audit.excluded
    assert "plan" in reason and "Varies / unable to answer" in reason


@pytest.mark.parametrize("field, kwargs", [
    ("name", {"name": "  "}),
    ("course code", {"course": "--"}),
    ("term", {"term": ""}),
])
def test_missing_required_values_exclude_the_row(tmp_path, field, kwargs):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(**kwargs)])
    (row, reason), = load_professor_responses(path, synthetic=False).audit.excluded
    assert reason == f"missing {field}"


def test_varies_becomes_unknown_never_a_number(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(answers=("4", "5", "Varies / unable to answer", "2", "4", "1"))])
    (entry,) = load_professor_responses(path, synthetic=False).entries
    assert entry.profile.values["plan"] is None


def test_resubmission_keeps_the_latest_and_reimport_is_stable(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [
        response(name="Dr. Twice", answers=("1",) * 6),
        response(name="dr.  twice", course="math130", term="spring 2027", answers=("5",) * 6),
    ])
    first = load_professor_responses(path, synthetic=False)
    assert len(first.entries) == 1
    assert list(first.entries[0].profile.values.values()) == [5] * 6
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
    assert real.entries[0].profile.source == "self-reported by the instructor via the ClassFit form (Spring 2027)"


# --------------------------------------------------------------------------- file-level rules

def test_microsoft_forms_export_with_extra_columns_and_bom(tmp_path):
    header = ["ID", "Start time", "Completion time", "Email", "Name"] + GOOGLE_HEADER[1:]
    row = ["1", "x", "y", "prof@example.edu", "Anonymous"] + response()[1:]
    path = write_csv(tmp_path, header, [row], encoding="utf-8-sig")
    (entry,) = load_professor_responses(path, synthetic=False).entries
    assert entry.name == "Dr. Test"
    assert "example.edu" not in str(entry)  # email column is ignored, never stored


def test_questions_can_be_reworded_after_their_number_and_topic(tmp_path):
    header = ["Timestamp"] + [h.split(" — ")[0] + " — completely reworded" for h in GOOGLE_HEADER[1:]]
    path = write_csv(tmp_path, header, [response()])
    assert len(load_professor_responses(path, synthetic=False).entries) == 1


def test_changed_topic_is_a_clear_file_error(tmp_path):
    header = [h.replace("Q7. Following the plan", "Q7. Schedule") for h in GOOGLE_HEADER]
    path = write_csv(tmp_path, header, [response()])
    with pytest.raises(FormImportError, match=r"Column Q7\. should start with 'Q7\. Following the plan'"):
        load_professor_responses(path, synthetic=False)


def test_version_1_export_is_rejected_with_a_migration_message(tmp_path):
    row = ["10/14/2026 10:00:00", "Dr. Old", "MATH 130", "Spring 2027", "", "2 — x", "4 — x", "1 — x", "5 — x", "", YES]
    path = write_csv(tmp_path, VERSION_1_HEADER, [row])
    with pytest.raises(FormImportError, match="questionnaire version 1.*cannot be converted"):
        load_professor_responses(path, synthetic=False)


def test_missing_required_column_is_a_clear_file_error(tmp_path):
    header = [h for h in GOOGLE_HEADER if not h.startswith("Q6.")]
    path = write_csv(tmp_path, header, [])
    with pytest.raises(FormImportError, match=r"No column starts with 'Q6\. Guided practice'"):
        load_professor_responses(path, synthetic=False)


def test_q1_prefix_does_not_match_q10_q11_or_q12(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(note="A note")])
    (entry,) = load_professor_responses(path, synthetic=False).entries
    assert entry.name == "Dr. Test" and entry.note == "A note"


def test_duplicate_question_numbers_are_rejected(tmp_path):
    header = GOOGLE_HEADER + ["Q5. Class discussion, asked twice"]
    path = write_csv(tmp_path, header, [])
    with pytest.raises(FormImportError, match="More than one column starts with 'Q5.'"):
        load_professor_responses(path, synthetic=False)


def test_empty_file_is_a_clear_error(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    with pytest.raises(FormImportError, match="empty"):
        load_professor_responses(path, synthetic=False)


# --------------------------------------------------------------------------- names and file encoding

def test_names_in_any_script_are_loaded(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(name="王老师"), response(name="Dr. José García")])
    result = load_professor_responses(path, synthetic=False)
    assert {e.name for e in result.entries} == {"王老师", "Dr. José García"}
    assert result.audit.excluded == ()


def test_names_differing_only_in_accents_are_different_people(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(name="Dr. Lé"), response(name="Dr. Lè")])
    result = load_professor_responses(path, synthetic=False)
    assert result.audit.loaded == 2 and result.audit.replaced == ()


def test_punctuation_only_name_counts_as_missing(tmp_path):
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(name="--")])
    assert load_professor_responses(path, synthetic=False).audit.excluded == ((2, "missing name"),)


def test_file_not_saved_as_utf8_gets_a_clear_message(tmp_path):
    # Excel's plain "CSV" option writes the answers' dash as a cp1252 byte.
    path = write_csv(tmp_path, GOOGLE_HEADER, [response(answers=("4 — Often", "5", "5", "2", "4", "1"))],
                     encoding="cp1252")
    with pytest.raises(FormImportError, match="CSV UTF-8"):
        load_professor_responses(path, synthetic=False)
