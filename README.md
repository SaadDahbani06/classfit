# Prof-Match

Prof-Match helps students compare sections of the same course based on what matters to them, and explains the tradeoffs before they register.

It is a content-based, rule-based comparison tool. It is not a trained machine-learning model, and its alignment score is not a grade prediction.

> **Status: M0 (scoring engine).** All data in this repository is synthetic. Course PM101 and Instructors A, B and C are fictional.

## Setup

Requires Python 3.10+ (developed and tested on 3.13.16).

```bash
cd prof-match
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run

```bash
pytest                                                    # run the tests
python -m profmatch.demo                                  # both demo students
python -m profmatch.demo --student 1                      # one demo student
python -m profmatch.demo --prefs 2,-,1,4 --weights 3,0,2,1  # your own inputs
```

Value order is always: format, assessment, collaboration, structure. Use `-` for "No preference" (its weight must be 0).

## How the score works

Each dimension uses a 1–5 scale (anchors in `src/profmatch/scale.py`). For student preference *p*, section value *x* and importance weight *w* (0–3):

```
similarity = 1 - |p - x| / 4
alignment  = 100 * Σ(w · similarity over rated dimensions with evidence) / W_known
coverage   = W_known / W
```

*W* is the total weight the student assigned; *W_known* is the weight on dimensions where the section actually has evidence.

**Missing data.** An unknown value stays unknown. It is never treated as 0 or as the midpoint 3. Only sections with evidence on every dimension the student rated are ranked. Sections with gaps go to a separate "More information needed" group, sorted by section ID, with their partial score shown for transparency only.

**Display and ties.** Scores are computed exactly (`fractions.Fraction`) and displayed as whole numbers rounded half-up. Sections with the same displayed score share a rank (1, 1, 3) and are listed by section ID.

**No preferences.** If every weight is 0, there is no score and no ranking, only a descriptive comparison.

## Layout

```
src/profmatch/
  scale.py         dimensions, anchors, importance levels (the instrument)
  validation.py    strict input checks; rejects rather than coerces
  models.py        StudentPreferences, SectionProfile (validate on creation)
  matching.py      scoring, missingness policy, ranking (pure functions)
  explanations.py  deterministic explanation templates
  synthetic.py     fictional PM101 fixtures
  demo.py          command-line demo
tests/             pytest suite
docs/PROGRESS.md   progress log
```

## Contributions

See `docs/PROGRESS.md`. Code in session 1 was drafted with an AI assistant (Claude) from Saad Eddine Dahbani's project handoff and verified by running the test suite.
