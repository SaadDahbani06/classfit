"""ClassFit (working name; package still called profmatch): explainable comparison
of sections of the same course.

A content-based, rule-based recommender: a fixed, documented formula compares a
student's stated preferences with instructors' descriptions of their course. Not a
trained machine-learning model, not AI, not a grade prediction.
"""

from .explanations import Explanation, explain
from .matching import (
    METHOD_VERSION,
    Comparison,
    MatchResult,
    compare_sections,
    score_section,
)
from .models import SectionProfile, StudentPreferences
from .validation import ValidationError

__all__ = [
    "METHOD_VERSION",
    "Comparison",
    "Explanation",
    "MatchResult",
    "SectionProfile",
    "StudentPreferences",
    "ValidationError",
    "compare_sections",
    "explain",
    "score_section",
]
