"""Questionnaire v2 definition tests: complete, parallel and explicit about its assumptions."""

from __future__ import annotations

from pathlib import Path

from profmatch.scale import (
    DIMENSIONS,
    NO_PREFERENCE_LABEL,
    QUESTIONNAIRE_VERSION,
    QUESTIONS,
    SCALE_MAX,
    UNKNOWN_ANSWER_LABEL,
)


def test_six_questions_in_a_fixed_order():
    assert QUESTIONNAIRE_VERSION == "v2"
    assert DIMENSIONS == ("discussion", "practice", "plan", "balance", "exams", "collaboration")


def test_every_question_has_five_distinct_labelled_answers():
    for q in QUESTIONS:
        assert len(q.answers) == SCALE_MAX, q.key
        shorts = [short for short, _ in q.answers]
        assert len(set(shorts)) == SCALE_MAX, q.key
        for short, full in q.answers:
            assert short and full.startswith(short), (q.key, short)
            assert short not in (NO_PREFERENCE_LABEL, UNKNOWN_ANSWER_LABEL)


def test_student_and_instructor_wording_is_parallel_and_tied_to_a_course_and_term():
    for q in QUESTIONS:
        assert q.student_question.endswith("?") and q.instructor_question.endswith("?")
        assert q.instructor_question.startswith("In this course and term, ")
        assert "would you like" in q.student_question
        assert q.definition.endswith(".")


def test_only_the_plan_question_is_flagged_as_unevenly_spaced():
    # The distance formula treats neighbouring answers as equally far apart; the
    # questionnaire must say where that is only an approximation.
    assert [q.key for q in QUESTIONS if not q.evenly_spaced] == ["plan"]


def test_instructor_form_doc_matches_the_instrument():
    # PROFESSOR_FORM.md (somewhere under docs/) is what organizers paste into the form tool; it must not drift.
    (path,) = (Path(__file__).resolve().parents[1] / "docs").rglob("PROFESSOR_FORM.md")
    doc = path.read_text(encoding="utf-8")
    for number, q in enumerate(QUESTIONS, start=5):
        assert f"**Q{number}. {q.topic} — {q.instructor_question}**" in doc
        assert f"Help text: {q.definition}" in doc
        for i, (_, full) in enumerate(q.answers, start=1):
            assert f"- {i} — {full}" in doc
    assert doc.count(f"- {UNKNOWN_ANSWER_LABEL}") == len(QUESTIONS)
