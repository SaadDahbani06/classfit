"""Command-line demo of the M0 engine on synthetic PM101 data.

    python -m profmatch.demo                      # both demo students
    python -m profmatch.demo --student 1          # one demo student
    python -m profmatch.demo --prefs 2,5,1,4 --weights 3,0,2,1
                                                  # your own inputs; use '-' for No preference

Order of values: format, assessment, collaboration, structure.
"""

from __future__ import annotations

import argparse
import sys

from .explanations import NO_CLOSE_MATCH, explain, format_percent
from .matching import (
    MODE_NO_PREFERENCES,
    MODE_NO_SECTIONS,
    MODE_RANKED,
    MODE_SINGLE_OPTION,
    MODE_UNRANKED_INCOMPLETE,
    Comparison,
    MatchResult,
    compare_sections,
)
from .models import StudentPreferences
from .scale import DIMENSIONS, IMPORTANCE_LABELS
from .synthetic import COURSE_CODE, COURSE_TITLE, DEMO_STUDENTS, PM101_SECTIONS
from .validation import ValidationError

BANNER = (
    "SYNTHETIC DEMO: fictional course and fictional instructors. Scores measure\n"
    "alignment with stated preferences. They are not grade predictions."
)

MODE_TEXT = {
    MODE_RANKED: "Ranked comparison of sections with complete evidence.",
    MODE_SINGLE_OPTION: "Only one section has complete evidence, so there is no meaningful ranking.",
    MODE_UNRANKED_INCOMPLETE: "No section has complete evidence: unranked comparison.",
    MODE_NO_PREFERENCES: "No dimension is rated: descriptive comparison, no scores.",
    MODE_NO_SECTIONS: "No sections to compare.",
}


def _fmt_exact(result: MatchResult) -> str:
    return "-" if result.alignment is None else f"{float(result.alignment):.3f}"


def _fmt_coverage(result: MatchResult) -> str:
    return "-" if result.coverage is None else format_percent(result.coverage)


def describe_student(prefs: StudentPreferences) -> str:
    parts = []
    for d in DIMENSIONS:
        value = prefs.values[d]
        weight = prefs.weights[d]
        shown = "no preference" if value is None else f"{value}, {IMPORTANCE_LABELS[weight]}"
        parts.append(f"{d}={shown}")
    return "; ".join(parts)


def render_comparison(comparison: Comparison, title: str, prefs: StudentPreferences) -> str:
    lines = [title, f"  {describe_student(prefs)}", f"  {MODE_TEXT[comparison.mode]}", ""]
    rank_of = {e.result.section_id: e.rank for e in comparison.ranked}

    header = f"  {'Rank':<5}{'Section':<10}{'Instructor':<26}{'Score':>6}{'Exact':>9}{'Coverage':>10}  Eligible to rank"
    lines += [header, "  " + "-" * (len(header) - 2)]
    ordered = [e.result for e in comparison.ranked] + [
        r for r in comparison.all_results if r.section_id not in rank_of
    ]
    for r in ordered:
        rank = str(rank_of.get(r.section_id, "-"))
        score = "-" if r.display_score is None else str(r.display_score)
        if r.section_id not in rank_of and r.display_score is not None:
            score += "*"
        eligible = "yes" if r.eligible_for_ranking else f"no ({r.status.replace('_', ' ')})"
        lines.append(
            f"  {rank:<5}{r.section_id:<10}{r.profile.instructor:<26}{score:>6}"
            f"{_fmt_exact(r):>9}{_fmt_coverage(r):>10}  {eligible}"
        )
    if any(r.display_score is not None and r.section_id not in rank_of for r in ordered):
        lines.append("  * partial score on incomplete evidence; shown for transparency, not ranked")

    lines += ["", "  Why these results?"]
    for r in ordered:
        exp = explain(r)
        lines.append(f"  [{r.section_id}] {exp.headline}")
        for reason in exp.reasons:
            lines.append(f"      + {reason}")
        if not exp.reasons and r.alignment is not None:
            lines.append(f"      ({NO_CLOSE_MATCH})")
        if exp.tradeoff:
            lines.append(f"      - {exp.tradeoff}")
        for missing in exp.missing:
            lines.append(f"      ? {missing}")
        for detail in exp.details:
            lines.append(f"        . {detail}")
    lines += ["", f"  Method version: {comparison.method_version}"]
    return "\n".join(lines)


def _parse_list(text: str, allow_none: bool) -> list[int | None]:
    items = [t.strip() for t in text.split(",")]
    parsed: list[int | None] = []
    for item in items:
        if allow_none and item in ("-", "none", "None"):
            parsed.append(None)
        else:
            try:
                parsed.append(int(item))
            except ValueError:
                raise ValidationError(f"Could not read {item!r} as a whole number.") from None
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prof-Match M0 demo on synthetic PM101 data.")
    parser.add_argument("--student", choices=sorted(DEMO_STUDENTS), help="run one demo student")
    parser.add_argument("--prefs", help="your preferences, e.g. 2,5,1,4 ('-' = no preference)")
    parser.add_argument("--weights", help="your importance weights 0-3, e.g. 3,3,2,1")
    args = parser.parse_args(argv)

    print("=" * 78)
    print(BANNER)
    print(f"Course: {COURSE_CODE}, {COURSE_TITLE}")
    print("=" * 78)

    try:
        if args.prefs or args.weights:
            if not (args.prefs and args.weights):
                raise ValidationError("Give both --prefs and --weights.")
            prefs = StudentPreferences.from_lists(
                _parse_list(args.prefs, allow_none=True), _parse_list(args.weights, allow_none=False)
            )
            runs = [("Custom student", prefs)]
        else:
            keys = [args.student] if args.student else sorted(DEMO_STUDENTS)
            runs = [(f"Demo student {k}", DEMO_STUDENTS[k]) for k in keys]
    except ValidationError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2

    for title, prefs in runs:
        print()
        print(render_comparison(compare_sections(prefs, PM101_SECTIONS), title, prefs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
