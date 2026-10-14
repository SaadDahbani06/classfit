"""Deterministic synthetic fixtures for software verification (roadmap sections H and Z).

EVERYTHING HERE IS FICTIONAL. Course PM101 and Instructors A, B and C do not exist.
These values were chosen to exercise the scoring rules (exact match, mismatch,
missing data); they are not survey responses and say nothing about real teaching.
"""

from __future__ import annotations

from .models import SectionProfile, StudentPreferences

SYNTHETIC_SOURCE = "synthetic fixture (fictional values for software testing, not real data)"
COURSE_CODE = "PM101"
COURSE_TITLE = "Prof-Match Demo Course (fictional)"

# Value order: format, assessment, collaboration, structure
SECTION_A = SectionProfile.from_lists(
    "PM101-01", COURSE_CODE, "Instructor A (fictional)", [2, 4, 1, 5], SYNTHETIC_SOURCE, True
)
SECTION_B = SectionProfile.from_lists(
    "PM101-02", COURSE_CODE, "Instructor B (fictional)", [5, 2, 4, 2], SYNTHETIC_SOURCE, True
)
SECTION_C = SectionProfile.from_lists(
    "PM101-03", COURSE_CODE, "Instructor C (fictional)", [2, None, 1, 5], SYNTHETIC_SOURCE, True
)
PM101_SECTIONS: tuple[SectionProfile, ...] = (SECTION_A, SECTION_B, SECTION_C)

# Student 1 wants: format 2, assessment 5, collaboration 1, structure 4
#   importance:    very (3), very (3), important (2), slightly (1)
STUDENT_1 = StudentPreferences.from_lists([2, 5, 1, 4], [3, 3, 2, 1])

# Student 2 has Section B's exact profile as preferences, same importance weights.
STUDENT_2 = StudentPreferences.from_lists([5, 2, 4, 2], [3, 3, 2, 1])

DEMO_STUDENTS: dict[str, StudentPreferences] = {"1": STUDENT_1, "2": STUDENT_2}
