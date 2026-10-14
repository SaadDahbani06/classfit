# Progress log

## 2026-10-14 — Session 2: surveys + website (simplified design)

**Design change (Saad's decision).** Simplest workable version: professors fill out a form describing their course; students answer the same four questions on a website; the engine matches them. The student "survey" is the website itself, and nothing a student enters is saved.

**Who did what.** Design direction: Saad. Code, form text and tests drafted by Claude (AI assistant); Saad to review, run and be able to explain. No teammate contributions yet.

### Completed
- `docs/PROFESSOR_FORM.md`: paste-ready form (Q1–Q10), consent wording, export steps, a draft invitation message for Saad to edit and send himself.
- `src/profmatch/forms.py`: imports Google/Microsoft Forms CSV exports. Finds columns by question number; skips rows without consent; "Not sure" → unknown; rejects unreadable answers; later resubmission replaces earlier; records every skipped/replaced row; SHA-256 fingerprint of the file; groups by course and term.
- `app.py`: Streamlit website. Course choice, four questions with importance, ranked cards with reasons/tradeoff/missing info, "Why this result?" breakdown, side-by-side table (the non-personalized baseline view), persistent synthetic/pilot banner, example-student buttons for demos, reset button.
- Synthetic demo responses in the exact export format (PM101: A–E, PM102: F–G, plus one no-consent row and one resubmission), and an empty template.
- Streamlit usage statistics turned off in `.streamlit/config.toml`.

### Verified (actually run)
- `pytest`: 154 passed (Python 3.13.16, pytest 9.1.1, Streamlit 1.66.0), including 7 headless website tests (Streamlit AppTest).
- Website flows: first load shows banner and no scores; example student 1 → A 89, E 78, D 61, B 28, C partial 96 unranked; example student 2 → B 100 first; one answered question → ranking; reset clears answers; second course loads.
- Importer mutation check: ignoring consent, turning "Not sure" into 3, and keeping the first submission each made tests fail.
- `streamlit run app.py` started and its health check answered "ok".
- **Not verified:** how the page looks. No browser was available in the build environment, so no screenshot was taken.

### Deviations from the roadmap
- Instructor self-reports only for now. Student experience reports (section J aggregation, medians, ≥5 threshold, conflicts) deferred; profiles are labeled "self-reported by the instructor".
- CSV import instead of a SQLite data model (section M). Simpler for one course; SQL can be added if the data grows or the résumé needs it.
- Schedule filtering still deferred.

### Unresolved
- Real responses live in gitignored `data/private/`, so a hosted copy of the site would not see them. Before deploying, decide how to publish consented responses (e.g., commit an approved file, or use hosting secrets).
- Deployment untested; not deployed.
- Form wording not yet tested with a professor.
- Organizer details, pilot course and interviews still open (see session 1).

### Next actions
1. Saad: run `streamlit run app.py`, click both example students, check layout on laptop and phone width.
2. Saad: create the form, fill it in once yourself as a test, export, and load it as pilot data.
3. Saad: ask 2–3 professors of one course to fill it out.
4. Next build: schedule conflicts (optional), deployment plan, evaluation logging for the user study.

---

## 2026-10-14 — Session 1: M0 scoring engine

**Who did what.** Code drafted by Claude (AI assistant) from Saad's handoff; Saad reviews, runs and must be able to explain it. No teammate contributions yet.

### Completed
- Project skeleton with `src/` layout, `pyproject.toml`, pinned dev dependencies, `.gitignore` that keeps private data and databases out of git.
- Strict input validation: ranges, whole numbers, booleans rejected, unknown/missing dimension keys rejected, "No preference" must carry weight 0, profile values must be finite numbers in [1, 5] or None.
- Section H scorer with exact arithmetic, coverage, complete-only ranking, shared ranks for equal displayed scores, and comparison modes (ranked, single option, unranked incomplete, no preferences, no sections).
- Guards against comparing sections from different courses or mixing synthetic and real profiles.
- Deterministic explanations: up to two reasons, one tradeoff, missing-evidence notes, full per-dimension breakdown, caveats.
- Synthetic PM101 fixtures (Instructors A, B, C) and a command-line demo.
- 106 tests.

### Verified (actually run)
- `pytest`: 106 passed (Python 3.13.16, Linux, pytest 9.1.1).
- Demo output matches section H: A = 88.889 → 89, B = 27.778 → 28, C = partial 95.833 → 96 at 67% coverage and not ranked; Student 2 → B = 100.
- Mutation check: deliberately breaking four rules (built-in `round()`, imputing unknown as 3, ranking partial sections, accepting booleans) each made tests fail.
- Fresh install from `requirements-dev.txt` in a clean copy: tests pass, demo runs.

### Decisions made (defensible, changeable)
| Decision | Reason |
|---|---|
| Round half-up, not Python `round()` | `round(62.5) == 62` (banker's rounding) would display inconsistently |
| Exact `Fraction` arithmetic | Rounding and ties can't flip because of float error |
| Competition ranking (1, 1, 3) | Common convention; makes clear how many sections beat you |
| Ties broken by section ID, using displayed score | Section H: tiny decimals must not pick a winner |
| Profile values may be non-integers (e.g. 3.5) | Medians of an even number of reports can fall between answers |
| "No preference" with weight > 0 is rejected | Contradictory input; reject rather than silently coerce |
| Reason = within 1 point; tradeoff = 2+ points apart | Simple, explainable thresholds; documented in `explanations.py` |
| Partial sections listed by ID, not partial score | Avoids implying a ranking among incomplete profiles |

### Deviations from the handoff layout
- Added `scale.py` (shared instrument definitions; avoids a circular import between models and validation).
- Added `pyproject.toml` (needed for the `src/` layout to install and import cleanly).
- Added `tests/test_validation.py` and `tests/test_explanations.py` alongside `test_matching.py`.
- Schedule filtering deferred to M1. Section A lists sections G–I for the first response, but sections Z, S and T place schedule filtering after M0; followed Z as instructed.
- Profile `source` is a single string for now. M2 replaces it with per-dimension evidence (source type, term, n, spread, conflict flag).

### Unresolved
- Organizer details not confirmed: registration deadline, pitch and Q&A length, slide and prototype rules, team rules.
- No pilot course verified; no interviews yet.
- Product name availability not checked.
- Tested only on Linux / Python 3.13; not yet run on Saad's machine.

### Next actions
1. Saad: run setup and tests locally; answer the comprehension questions.
2. M1 part 1: schedule filtering (`scheduling.py`) with section I's interval rules and tests.
3. M1 part 2: minimal Streamlit flow using the engine unchanged.
4. In parallel (Saad): send organizer questions; line up ~5 interviews before the Oct 18 gate.
