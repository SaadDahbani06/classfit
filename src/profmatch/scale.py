"""The measurement instrument: dimensions, scale anchors and importance levels (roadmap section G).

Everything that defines *what the numbers mean* lives here, so the scorer, the
explanations, the future Streamlit questions and the future survey forms all use
one shared definition. If the wording of an anchor changes, it changes here.

Design note: the 1-5 scale is ordinal. Treating the distance between 1 and 2 as
equal to the distance between 4 and 5 is a modelling assumption that makes a
simple distance model possible; it is not a measured fact.
"""

from __future__ import annotations

# Order matters: it is the column order for list-based inputs and the
# tie-breaking order for explanations. Do not reorder without updating tests.
DIMENSIONS: tuple[str, ...] = ("format", "assessment", "collaboration", "structure")

SCALE_MIN = 1
SCALE_MAX = 5
SCALE_SPAN = SCALE_MAX - SCALE_MIN  # 4: the largest possible gap between two answers

WEIGHT_MIN = 0
WEIGHT_MAX = 3

DIMENSION_LABELS: dict[str, str] = {
    "format": "class format",
    "assessment": "assessment distribution",
    "collaboration": "collaboration on assessed work",
    "structure": "advance structure",
}

DIMENSION_QUESTIONS: dict[str, str] = {
    "format": "Which class format do you prefer?",
    "assessment": "How do you prefer graded work to be distributed?",
    "collaboration": "How do you prefer assessed assignments?",
    "structure": "How much advance structure do you prefer?",
}

# Anchors for 1, 3 and 5. Values 2 and 4 are described as "between" two anchors.
# Neither end of any scale is better; "structure" is not a quality rating.
SCALE_ANCHORS: dict[str, dict[int, str]] = {
    "format": {
        1: "mostly lecture",
        3: "roughly balanced",
        5: "mostly discussion/interactive activities",
    },
    "assessment": {
        1: "a few major assessments",
        3: "a mixture",
        5: "frequent smaller assessments",
    },
    "collaboration": {
        1: "mostly individual",
        3: "mixed",
        5: "mostly group work",
    },
    "structure": {
        1: "flexible, evolving plans",
        3: "some fixed structure",
        5: "detailed schedules/instructions in advance",
    },
}

IMPORTANCE_LABELS: dict[int, str] = {
    0: "no preference",
    1: "slightly important",
    2: "important",
    3: "very important",
}
