"""Import instructor survey responses exported from Google Forms or Microsoft Forms.

How columns are found: every form question starts with a number ("Q1. Your name").
The six practice questions also start with their topic ("Q5. Class discussion —
In this course and term, ..."), so the rest of a question can be reworded without
breaking the import, but a file from questionnaire version 1 (whose Q5-Q8 asked
different questions) can never be read as version 2. Extra columns the form tool
adds (Timestamp, Email, ID, Start time, ...) are ignored and never displayed.

What gets loaded: only rows whose consent answer (Q12) starts with "Yes". Every
skipped row is recorded with its spreadsheet row number and a reason, so nothing
disappears silently. Invalid answers are rejected, not guessed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .branding import PRODUCT_NAME
from .models import SectionProfile
from .scale import DIMENSIONS, QUESTIONS, UNKNOWN_ANSWER_LABEL
from .validation import ValidationError

# Field -> start of the form question title (see the instructor form, docs/INSTRUCTOR_FORM.md).
QUESTION_PREFIXES: dict[str, str] = {
    "name": "Q1.",
    "course": "Q2.",
    "term": "Q3.",
    "sections": "Q4.",
    **{q.key: f"Q{number}. {q.topic}" for number, q in enumerate(QUESTIONS, start=5)},
    "note": "Q11.",
    "consent": "Q12.",
}
OPTIONAL_FIELDS = {"sections", "note"}

UNKNOWN_PREFIXES = ("varies", "unable")  # "Varies / unable to answer"
CONSENT_PREFIX = "yes"

VERSION_1_MESSAGE = (
    "This file comes from questionnaire version 1 (Q5–Q8: class format, assessment distribution, "
    "collaboration, structure). Version 2 asks six different questions, so version-1 answers cannot "
    "be converted. Collect new responses with the version-2 form (docs/INSTRUCTOR_FORM.md)."
)

# An answer like "3", "3 — Roughly balanced", "3 - mixed" or "3: ...": a single
# digit 1-5 that is not part of a longer number such as "35" or "3.5".
_ANSWER_PATTERN = re.compile(r"^([1-5])(?:\s*$|\s*[—–\-:)]|\s+\D)")


class FormImportError(ValueError):
    """The file as a whole cannot be imported (missing or ambiguous columns, empty file)."""


@dataclass(frozen=True)
class ProfessorEntry:
    row_number: int        # spreadsheet row (header is row 1), so you can find it in Sheets/Excel
    name: str
    course: str            # display form, e.g. "MATH 130"
    course_key: str        # grouping key, e.g. "MATH130"
    term: str              # display form, e.g. "Spring 2027"
    term_key: str          # grouping key, e.g. "spring 2027"
    sections: str
    note: str
    profile: SectionProfile


@dataclass(frozen=True)
class ImportAudit:
    file_name: str
    file_sha256: str
    rows_read: int
    loaded: int
    excluded: tuple[tuple[int, str], ...]  # (row number, reason)
    replaced: tuple[tuple[int, int], ...]  # (earlier row, later row that replaced it)


@dataclass(frozen=True)
class ImportResult:
    entries: tuple[ProfessorEntry, ...]
    audit: ImportAudit
    is_synthetic: bool


def parse_scale_answer(dimension: str, cell: str | None) -> int | None:
    """'4 — Often (61–80% of class sessions)' -> 4; 'Varies / unable to answer' or blank -> None."""
    text = (cell or "").strip()
    if not text or text.casefold().startswith(UNKNOWN_PREFIXES):
        return None
    match = _ANSWER_PATTERN.match(text)
    if not match:
        raise ValidationError(
            f"{dimension}: could not read {text!r}; expected an answer starting with 1-5, "
            f"or '{UNKNOWN_ANSWER_LABEL}'."
        )
    return int(match.group(1))


def course_key(course: str) -> str:
    """'math 130', 'MATH-130' and 'MATH130' all become 'MATH130'."""
    return re.sub(r"[^A-Z0-9]", "", course.upper())


def course_display(key: str) -> str:
    """'MATH130' -> 'MATH 130'."""
    match = re.match(r"^([A-Z]+)(\d.*)$", key)
    return f"{match.group(1)} {match.group(2)}" if match else key


def _normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def _slug(text: str) -> str:
    """'Dr. Jane Smith' -> 'dr-jane-smith'. Letters from every script are kept, so a name
    written in, say, Chinese, Arabic or Hindi is not mistaken for a missing name, and two
    names that differ only in accented letters are never merged into one person."""
    text = unicodedata.normalize("NFKC", text).casefold()
    kept = "".join(c if c.isalnum() or unicodedata.category(c).startswith("M") else " " for c in text)
    return "-".join(kept.split())


def _is_version_1(header: list[str]) -> bool:
    # Version 1's last question was consent: "Q10. May Prof-Match show your name ...".
    return any(h.strip().casefold().startswith("q10.") and "show your name" in h.casefold() for h in header)


def _locate_columns(header: list[str]) -> dict[str, int]:
    if _is_version_1(header):
        raise FormImportError(VERSION_1_MESSAGE)
    located: dict[str, int] = {}
    for field, prefix in QUESTION_PREFIXES.items():
        number = prefix.split(" ", 1)[0]  # "Q5."
        hits = [i for i, h in enumerate(header) if h.strip().casefold().startswith(number.casefold())]
        if len(hits) > 1:
            raise FormImportError(f"More than one column starts with {number!r}; keep each question number unique.")
        if not hits:
            if field in OPTIONAL_FIELDS:
                continue
            raise FormImportError(
                f"No column starts with {prefix!r} ({field}). Each form question title must begin with its "
                "number (and, for Q5–Q10, its topic), e.g. 'Q5. Class discussion — In this course and term, "
                "...'. See docs/INSTRUCTOR_FORM.md."
            )
        title = header[hits[0]].strip()
        if not title.casefold().startswith(prefix.casefold()):
            raise FormImportError(
                f"Column {number} should start with {prefix!r} but is {title!r}. Keep each question's number "
                "and topic at the start of its title; see docs/INSTRUCTOR_FORM.md."
            )
        located[field] = hits[0]
    return located


def load_professor_responses(path: str | Path, *, synthetic: bool) -> ImportResult:
    """Read one exported response file. ``synthetic`` labels the whole file: a file is
    either synthetic demo data or real pilot data, never a mix."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig drops the byte-order mark Excel adds
    except UnicodeDecodeError as error:
        raise FormImportError(
            f"{path.name} is not saved as UTF-8 text. In Excel, use File > Save As > 'CSV UTF-8' "
            "(plain 'CSV' breaks characters such as the dash in the answer options)."
        ) from error
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as error:
        raise FormImportError(f"{path.name} could not be read as a CSV file: {error}.") from error
    if not rows:
        raise FormImportError(f"{path.name} is empty.")
    header, data_rows = rows[0], rows[1:]
    columns = _locate_columns(header)

    excluded: list[tuple[int, str]] = []
    replaced: list[tuple[int, int]] = []
    latest: dict[tuple[str, str, str], ProfessorEntry] = {}
    rows_read = 0

    for offset, row in enumerate(data_rows):
        row_number = offset + 2
        if not any(cell.strip() for cell in row):
            continue  # blank line at the end of an export
        rows_read += 1
        row = row + [""] * (len(header) - len(row))

        def cell(field: str) -> str:
            return row[columns[field]].strip() if field in columns else ""

        # Consent first: rows without it are not examined further.
        if not cell("consent").casefold().startswith(CONSENT_PREFIX):
            excluded.append((row_number, "no consent to display"))
            continue

        name, course, term = _normalize_spaces(cell("name")), cell("course"), _normalize_spaces(cell("term"))
        missing = [label for label, value in (("name", _slug(name)), ("course code", course_key(course)),
                                              ("term", term)) if not value]
        if missing:
            excluded.append((row_number, f"missing {', '.join(missing)}"))
            continue

        try:
            values = {d: parse_scale_answer(d, cell(d)) for d in DIMENSIONS}
        except ValidationError as error:
            excluded.append((row_number, f"invalid answer: {error}"))
            continue

        key_course, key_term = course_key(course), term.casefold()
        source = (
            "synthetic demo response (fictional instructor, not real data)"
            if synthetic
            else f"self-reported by the instructor via the {PRODUCT_NAME} form ({term})"
        )
        entry = ProfessorEntry(
            row_number=row_number,
            name=name,
            course=course_display(key_course),
            course_key=key_course,
            term=term,
            term_key=key_term,
            sections=_normalize_spaces(cell("sections")),
            note=cell("note"),
            profile=SectionProfile(
                section_id=f"{key_course}-{_slug(name)}",
                course_code=key_course,
                instructor=name,
                values=values,
                source=source,
                is_synthetic=synthetic,
            ),
        )
        identity = (key_course, key_term, _slug(name))
        if identity in latest:  # same person, course and term: the later submission wins
            replaced.append((latest[identity].row_number, row_number))
        latest[identity] = entry

    entries = tuple(sorted(latest.values(), key=lambda e: (e.course_key, e.term_key, e.profile.section_id)))
    audit = ImportAudit(
        file_name=path.name,
        file_sha256=hashlib.sha256(raw).hexdigest(),
        rows_read=rows_read,
        loaded=len(entries),
        excluded=tuple(excluded),
        replaced=tuple(replaced),
    )
    return ImportResult(entries, audit, synthetic)


def group_by_course(entries: tuple[ProfessorEntry, ...]) -> dict[tuple[str, str], tuple[ProfessorEntry, ...]]:
    """Group entries by (course, term). Different courses or terms are never pooled."""
    groups: dict[tuple[str, str], list[ProfessorEntry]] = {}
    for entry in entries:
        groups.setdefault((entry.course_key, entry.term_key), []).append(entry)
    return {key: tuple(groups[key]) for key in sorted(groups)}


def group_label(group: tuple[ProfessorEntry, ...]) -> str:
    first = group[0]
    return f"{first.course} · {first.term}"
