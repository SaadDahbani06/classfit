"""Deterministic synthetic fixtures for software verification and the demo.

EVERYTHING HERE IS FICTIONAL. Course PM101 and Instructors A–E do not exist.
These values were chosen to exercise the scoring rules (close answers, tradeoffs,
an unanswered question, contrasting students); they are not survey responses and
say nothing about real teaching. data/demo/professor_responses_demo.csv contains
the same PM101 answers in the form-export format, and a test keeps the two equal.
"""

from __future__ import annotations

from .models import SectionProfile, StudentPreferences

SYNTHETIC_SOURCE = "synthetic fixture (fictional values for software testing, not real data)"
COURSE_CODE = "PM101"
COURSE_TITLE = "ClassFit Demo Course (fictional)"

# Value order: discussion, practice, plan, balance, exams, collaboration (None = "Varies / unable to answer")
SECTION_A = SectionProfile.from_lists(
    "PM101-01", COURSE_CODE, "Instructor A (fictional)", [4, 5, 5, 2, 4, 1], SYNTHETIC_SOURCE, True
)
SECTION_B = SectionProfile.from_lists(
    "PM101-02", COURSE_CODE, "Instructor B (fictional)", [5, 1, 2, 4, 1, 5], SYNTHETIC_SOURCE, True
)
SECTION_C = SectionProfile.from_lists(
    "PM101-03", COURSE_CODE, "Instructor C (fictional)", [4, 3, None, 4, 2, 4], SYNTHETIC_SOURCE, True
)
SECTION_D = SectionProfile.from_lists(
    "PM101-04", COURSE_CODE, "Instructor D (fictional)", [3, 3, 3, 3, 3, 3], SYNTHETIC_SOURCE, True
)
SECTION_E = SectionProfile.from_lists(
    "PM101-05", COURSE_CODE, "Instructor E (fictional)", [4, 4, 4, 3, 2, 2], SYNTHETIC_SOURCE, True
)
PM101_SECTIONS: tuple[SectionProfile, ...] = (SECTION_A, SECTION_B, SECTION_C, SECTION_D, SECTION_E)

# Student 1 wants: discussion 5, practice 3, plan (no preference), balance 4, exams 1, collaboration 4
#   importance:    very (3), slightly (1), -, important (2), very (3), important (2)
STUDENT_1 = StudentPreferences.from_lists([5, 3, None, 4, 1, 4], [3, 1, 0, 2, 3, 2])

# Student 2 wants: discussion 2, practice 5, plan 5, balance 3, exams 4, collaboration 2
#   importance:    slightly (1), very (3), very (3), slightly (1), important (2), important (2)
STUDENT_2 = StudentPreferences.from_lists([2, 5, 5, 3, 4, 2], [1, 3, 3, 1, 2, 2])

DEMO_STUDENTS: dict[str, StudentPreferences] = {"1": STUDENT_1, "2": STUDENT_2}

# One-line summaries of what each fictional student said they want *for this course*.
# Preferences are contextual, so these describe answers, not types of learner.
DEMO_STUDENT_SUMMARIES: dict[str, str] = {
    "1": "Wants frequent discussion and group work, with few timed exams. No preference on following the plan.",
    "2": "Wants lots of guided practice and a plan that is followed closely; fine with exams.",
}
