# ClassFit (working name)

**Same course. Different experience. Find your fit.**

ClassFit helps students compare sections of the same course by how each is taught. Instructors describe their classroom practices for one course and term; students say what they prefer for that course; ClassFit shows how closely each section matches, with the tradeoffs spelled out.

```
Instructor form (Google/Microsoft Forms) ──► exported CSV ──► importer (checks + audit)
                                                                      │
Student answers the same 6 questions on the website ──► matching engine ◄┘
                                                              │
                                    sections ordered by alignment + explanations
```

It is a rule-based comparison with a fixed, published formula. It is not machine learning or AI. The alignment score measures agreement between questionnaire answers: it is not a grade prediction or a rating of teaching quality. Instructor answers are self-reported.

> **Status:** working website on synthetic data, questionnaire v2. Courses PM101/PM102 and Instructors A–H are fictional. No real instructor or student has used it yet. "ClassFit" is a working name; availability has not been checked. The fox mark is an original drawing, not Marist University's official Red Fox logo. The Python package is still called `profmatch`.

## Setup

Requires Python 3.10+ (developed and tested on 3.13.16).

```bash
cd classfit
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run

```bash
streamlit run app.py               # the website; opens in your browser
pytest                             # all tests (205)
python -m profmatch.demo           # command-line version of the engine
```

**Two-student demo:** in the sidebar, click **Example student 1**, then **Example student 2**, or use the buttons on the page. Both students are fictional and want different things from the same course, so their closest matches differ (Instructor B for student 1, Instructor A for student 2). A script for presenting it is in the Pitch Pack PDF.

## View it on a phone

1. Run `streamlit run app.py` on the laptop and keep the terminal open. The terminal prints a **Network URL**, such as `http://148.100.138.163:8501`.
2. On a phone connected to the **same Wi-Fi**, type that address into the browser. If the Mac asks whether Python may accept incoming connections, click **Allow**.
3. If the page doesn't load, the Wi-Fi probably blocks devices from reaching each other (common on campus networks). Turn on the phone's Personal Hotspot, connect the laptop to it, restart the app, and open the new Network URL on the phone.

To preview the phone layout without a phone: in Chrome press Cmd+Option+I, then Cmd+Shift+M. For a permanent link anyone can open, the app has to be hosted, for example on Streamlit Community Cloud (not set up yet).

## The questionnaire (v2)

Six questions, each with five labelled answers that students and instructors share:

1. Class discussion
2. Guided practice
3. Following the plan
4. Concepts and applications
5. Timed quizzes and exams
6. Collaborative graded work

Students can choose "No preference" and rate how important each answer is (1–3). Instructors answer for one course in one term and can choose "Varies / unable to answer", which is never guessed. Instructors can also add an optional note, which is shown but not scored. Wording, rationale, evaluation and versioning are in the Questionnaire PDF; the paste-ready form is in the Instructor Form PDF.

## Using real instructor responses

1. Build the form from the Instructor Form PDF (keep each title's `Q1.`–`Q12.` number, and the topic for Q5–Q10).
2. Export responses as CSV and save them as `data/private/professor_responses.csv`.
3. Refresh the website: real responses are shown automatically. To check skipped rows or switch back to the demo, open the site with `?admin=1` at the end of the address (for example `http://localhost:8501/?admin=1`) and use **Technical details** in the sidebar. Students never see that section.

`data/private/` is excluded from git. The importer handles responses like this:
- rows without consent are skipped;
- "Varies / unable to answer" stays unknown;
- a resubmission replaces the earlier one;
- a version-1 export is refused instead of being converted;
- every skipped row is listed under **Technical details** (with `?admin=1`) with its reason.

## How the score works

Each question has five ordered answers. For student answer *s*, instructor answer *p* and importance *w* (1–3):

```
similarity = 1 - |p - s| / 4
alignment  = 100 * Σ(w · similarity) / Σ(w)          over questions both sides answered
           = 100 * [1 - Σ(w · |p - s|) / (4 · Σw)]
```

**Equal steps.** Counting steps treats neighbouring answers as equally far apart. Five questions use equal-width ranges (0–20%, 21–40%, …), so that is a fair approximation. "Following the plan" uses ordered descriptions with uneven real gaps, so its distances are a simplification. No question is categorical.

**Missing answers.** "No preference" questions are left out. An instructor's "Varies / unable to answer" stays unknown (never treated as 3), and only instructors who answered every question the student rated are ranked. The others appear under "More information needed", with their partial score in the text.

**Explanations.** Every rated question is explained exactly once:
- close (within 1 step);
- tradeoff (2 or more steps apart);
- not comparable (no answer from the instructor).

Each card also shows the formula with the student's numbers.

**Display and ties.** Scores are computed exactly (`fractions.Fraction`) and shown as whole numbers, rounded half-up. Equal displayed scores share a rank (1, 1, 3) and are listed by section ID.

## Privacy

The website uses a student's answers only to show results. They live in Streamlit's server memory for that browser session and are never written to a file or database. Streamlit may discard a disconnected session after `server.disconnectedSessionTTL` (default 120 seconds), and a test checks that using the app creates no files. Usage statistics are off (`.streamlit/config.toml`). A hosting service may keep its own access logs, so a hosted copy needs a privacy notice that names the host.

## Layout

```
app.py             the website (display only; no scoring logic)
.streamlit/        base theme and privacy settings (component styles are in app.py)
assets/            the ClassFit fox mark (SVG, and a PNG for the browser tab)
scripts/           record_demo.py: records the demo walkthrough
src/profmatch/
  branding.py      product name and tagline (one place to rename)
  scale.py         questionnaire v2: questions, answers, importance levels, version
  validation.py    strict input checks
  models.py        StudentPreferences, SectionProfile
  matching.py      scoring, missing-answer policy, ranking
  explanations.py  deterministic explanation text
  forms.py         imports form exports, refuses version 1, audits skipped rows
  synthetic.py     fictional fixtures and the two demo students
  demo.py          command-line demo
data/demo/         synthetic responses in the same format as a real export
data/templates/    empty spreadsheet with the form's columns
docs/design/       screenshots of the current design
docs/INSTRUCTOR_FORM.md  the instructor survey to paste into Google or Microsoft Forms
tests/             pytest suite, including headless website tests
```

## Contributions

Built and pitched with Ariel Alter and Giorgi Siordia for the Marist Innovation Challenge. Code was drafted with an AI assistant (Claude) from Saad Eddine Dahbani's design and project handoff, and verified by running the test suite.
