"""The measurement instrument: questionnaire version 2, six classroom practices.

Everything that defines *what the numbers mean* lives here, so the scorer, the
explanations, the website and the instructor form all use one definition. If the
wording of an answer changes, it changes here and in the instructor form (PROFESSOR_FORM.md).

Version 2 replaced version 1's four questions (class format, assessment
distribution, collaboration, structure). The constructs differ, so version-1
answers are never converted to version 2; the importer rejects version-1 files.
See the questionnaire document (QUESTIONNAIRE.md), "Versioning".

Design notes:
- Students and instructors see the same five answers; only the question stem
  differs ("would you like" vs "in this course and term").
- Every question is ordinal and no answer is better than another. Five questions
  use equal-width ranges (0-20%, 21-40%, ...), so treating neighbouring answers
  as equally far apart is a reasonable approximation. "Following the plan" uses
  ordered descriptions whose real-world gaps are uneven, so distances there are a
  simplification (``evenly_spaced=False``).
- Students may answer "No preference" (left out of the score). Instructors may
  answer "Varies / unable to answer" (unknown, never guessed).
"""

from __future__ import annotations

from dataclasses import dataclass

QUESTIONNAIRE_VERSION = "v2"

SCALE_MIN = 1
SCALE_MAX = 5
SCALE_SPAN = SCALE_MAX - SCALE_MIN  # 4: the largest possible gap between two answers

WEIGHT_MIN = 0
WEIGHT_MAX = 3

NO_PREFERENCE_LABEL = "No preference"           # student option, weight 0
UNKNOWN_ANSWER_LABEL = "Varies / unable to answer"  # instructor option, stored as None


@dataclass(frozen=True)
class Question:
    key: str
    label: str                # used inside sentences: "Close on class discussion: ..."
    topic: str                # title-case name; also the form column's topic ("Q5. Class discussion")
    student_question: str
    instructor_question: str
    definition: str           # shown to both audiences
    answers: tuple[tuple[str, str], ...]  # (short, full) for answers 1..5
    evenly_spaced: bool


_GRADE_SHARES = (
    ("0–20%", "0–20% of the course grade"),
    ("21–40%", "21–40% of the course grade"),
    ("41–60%", "41–60% of the course grade"),
    ("61–80%", "61–80% of the course grade"),
    ("81–100%", "81–100% of the course grade"),
)

# Order matters: it is the column order for list-based inputs and the tie-breaking
# order for explanations. Do not reorder without updating fixtures and tests.
QUESTIONS: tuple[Question, ...] = (
    Question(
        key="discussion",
        label="class discussion",
        topic="Class discussion",
        student_question="How often would you like class sessions to include discussion?",
        instructor_question="In this course and term, how often do class sessions include discussion?",
        definition="Discussion means students talking through ideas with each other or the whole class, "
                   "beyond quick questions and answers.",
        answers=(
            ("Rarely", "Rarely (0–20% of class sessions)"),
            ("Sometimes", "Sometimes (21–40% of class sessions)"),
            ("About half", "About half (41–60% of class sessions)"),
            ("Often", "Often (61–80% of class sessions)"),
            ("Almost always", "Almost always (81–100% of class sessions)"),
        ),
        evenly_spaced=True,
    ),
    Question(
        key="practice",
        label="guided practice",
        topic="Guided practice",
        student_question="How much class time would you like spent on guided practice?",
        instructor_question="In this course and term, how much class time is spent on guided practice?",
        definition="Guided practice means students working on problems or tasks during class while the "
                   "instructor (or a TA) helps and gives feedback.",
        answers=(
            ("Little", "Little (0–20% of class time)"),
            ("Some", "Some (21–40% of class time)"),
            ("About half", "About half (41–60% of class time)"),
            ("Most", "Most (61–80% of class time)"),
            ("Nearly all", "Nearly all (81–100% of class time)"),
        ),
        evenly_spaced=True,
    ),
    Question(
        key="plan",
        label="following the plan",
        topic="Following the plan",
        student_question="How closely would you like classes to follow the plan shared at the start of the term?",
        instructor_question="In this course and term, how closely do classes follow the plan shared at the "
                            "start of the term?",
        definition="The plan is the schedule of topics, readings and due dates students receive at the "
                   "start of the term.",
        answers=(
            ("Set as we go", "Set as we go (no dated schedule at the start)"),
            ("Changes often", "Changes often (the dated schedule changes most weeks)"),
            ("Changes sometimes", "Changes sometimes (the dated schedule changes every few weeks)"),
            ("Changes rarely", "Changes rarely (the dated schedule changes once or twice a term)"),
            ("Followed closely", "Followed closely (a detailed dated schedule, kept as published)"),
        ),
        evenly_spaced=False,
    ),
    Question(
        key="balance",
        label="concepts and applications",
        topic="Concepts and applications",
        student_question="What balance of concepts and applications would you like in class?",
        instructor_question="In this course and term, what is the balance of concepts and applications in class?",
        definition="Concepts are ideas, theory and why things work. Applications are using those ideas on "
                   "real problems, cases, data or projects.",
        answers=(
            ("Mostly concepts", "Mostly concepts (over 80% of class time on concepts)"),
            ("More concepts", "More concepts (about 60–80% on concepts)"),
            ("Even balance", "Even balance (about 40–60% on each)"),
            ("More applications", "More applications (about 60–80% on applications)"),
            ("Mostly applications", "Mostly applications (over 80% of class time on applications)"),
        ),
        evenly_spaced=True,
    ),
    Question(
        key="exams",
        label="timed quizzes and exams",
        topic="Timed quizzes and exams",
        student_question="What share of your course grade would you like to come from timed quizzes and exams?",
        instructor_question="In this course and term, what share of the course grade comes from timed quizzes "
                            "and exams?",
        definition="Timed means completed within a set time limit, in class or online: quizzes, midterms "
                   "and finals.",
        answers=_GRADE_SHARES,
        evenly_spaced=True,
    ),
    Question(
        key="collaboration",
        label="collaborative graded work",
        topic="Collaborative graded work",
        student_question="What share of your course grade would you like to come from work done with other "
                         "students?",
        instructor_question="In this course and term, what share of the course grade comes from work students "
                            "complete together?",
        definition="Work done together means graded group projects, team assignments or pair work that "
                   "students are asked to complete with others.",
        answers=_GRADE_SHARES,
        evenly_spaced=True,
    ),
)

QUESTION_BY_KEY: dict[str, Question] = {q.key: q for q in QUESTIONS}
DIMENSIONS: tuple[str, ...] = tuple(q.key for q in QUESTIONS)
DIMENSION_LABELS: dict[str, str] = {q.key: q.label for q in QUESTIONS}

IMPORTANCE_LABELS: dict[int, str] = {
    0: "no preference",
    1: "slightly important",
    2: "important",
    3: "very important",
}
