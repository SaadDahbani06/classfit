# Prof-Match

Prof-Match helps students compare sections of the same course based on what matters to them, and explains the tradeoffs before they register.

```
Professor form (Google/Microsoft Forms) ──► exported CSV ──► importer (checks + audit)
                                                                     │
Student answers 4 questions on the website ──► matching engine ◄─────┘
                                                     │
                                       ranked matches + explanations
```

It is a content-based, rule-based comparison tool. It is not a trained machine-learning model, and its alignment score is not a grade prediction. Instructor answers are self-reported.

> **Status:** working website on synthetic data. Course PM101/PM102 and Instructors A–H are fictional.

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
streamlit run app.py               # the website; opens in your browser
pytest                             # all tests
python -m profmatch.demo           # command-line version of the engine
```

On the website, use **Try an example** in the sidebar to load demo students 1 and 2.

## Using real professor responses

1. Build the form from `docs/PROFESSOR_FORM.md` (keep the `Q1.`–`Q10.` numbers).
2. Export responses as CSV and save them as `data/private/professor_responses.csv`.
3. Refresh the website and choose **Pilot data** in the sidebar.

`data/private/` is excluded from git. Rows without consent are skipped, "Not sure" stays unknown, a resubmission replaces the earlier one, and every skipped row is listed under **Data status** with its reason.

## How the score works

Each question uses a 1–5 scale. For student answer *s*, instructor answer *p* and importance *w* (1–3):

```
similarity = 1 - |p - s| / 4
alignment  = 100 * Σ(w · similarity) / Σ(w)        over questions the student rated
```

In matrix form, with every instructor's answers stacked as rows of *P*:
`scores = 100 · (1 − |P − s| · w / (4 · Σw))`. It measures the gap between answers rather than multiplying them, because a plain dot product would rank a 5 above a 1 for a student who answered 1.

**Missing data.** "Not sure" stays unknown; it is never treated as 3. Only instructors with answers to every question the student rated are ranked; the rest appear under "More information needed" with a partial score for transparency.

**Display and ties.** Scores are computed exactly (`fractions.Fraction`) and shown as whole numbers rounded half-up. Equal displayed scores share a rank (1, 1, 3) and are listed alphabetically.

## Layout

```
app.py             the website (display only; no scoring logic)
src/profmatch/
  scale.py         questions, 1–5 anchors, importance levels
  validation.py    strict input checks
  models.py        StudentPreferences, SectionProfile
  matching.py      scoring, missing-data policy, ranking
  explanations.py  deterministic explanation text
  forms.py         imports form exports, with an audit of skipped rows
  synthetic.py     fictional fixtures used by tests and the CLI demo
  demo.py          command-line demo
data/demo/         synthetic responses in the same format as a real export
data/templates/    empty spreadsheet with the form's columns
docs/              professor form, progress log
tests/             pytest suite, including headless website tests
```

## Contributions

See `docs/PROGRESS.md`. Code was drafted with an AI assistant (Claude) from Saad Eddine Dahbani's design and project handoff, and verified by running the test suite.
