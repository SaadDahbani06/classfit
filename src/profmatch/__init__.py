"""Prof-Match: explainable comparison of sections of the same course.

A content-based, rule-based recommender. Not a trained machine-learning model,
not a grade prediction.
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
