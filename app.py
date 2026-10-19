"""Prof-Match website. Run with:  streamlit run app.py

This file only collects input and displays results. Every score and every
sentence of explanation comes from the profmatch package, so the website can
never disagree with the tested engine. Nothing a student enters is saved.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
# Find the profmatch package in src/ even if `pip install -r requirements.txt` was skipped.
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from profmatch.explanations import NO_CLOSE_MATCH, NOT_A_PREDICTION, describe_value, explain
from profmatch.forms import (
    FormImportError,
    ImportResult,
    ProfessorEntry,
    group_by_course,
    group_label,
    load_professor_responses,
)
from profmatch.matching import (
    MODE_NO_PREFERENCES,
    MODE_RANKED,
    MODE_SINGLE_OPTION,
    MODE_UNRANKED_INCOMPLETE,
    MatchResult,
    compare_sections,
)
from profmatch.models import StudentPreferences
from profmatch.scale import DIMENSION_LABELS, DIMENSION_QUESTIONS, DIMENSIONS, IMPORTANCE_LABELS, SCALE_ANCHORS
from profmatch.synthetic import DEMO_STUDENTS
from profmatch.validation import ValidationError

DEMO_FILE = ROOT / "data" / "demo" / "professor_responses_demo.csv"
PILOT_FILE = ROOT / "data" / "private" / "professor_responses.csv"
DEMO, PILOT = "Synthetic demo", "Pilot data"
NO_PREFERENCE = 0  # selectbox value meaning "No preference"

st.set_page_config(page_title="Prof-Match · Red Foxes", page_icon="🦊", layout="centered")

MARIST_RED = "#C8102E"
STYLE = f"""
<style>
.pm-hero {{
  background: linear-gradient(135deg, {MARIST_RED} 0%, #8E0B21 100%);
  color: #fff; border-radius: 1.1rem; padding: 1.6rem 1.75rem 1.4rem;
  margin-bottom: .5rem; position: relative; overflow: hidden;
  box-shadow: 0 10px 30px -12px rgba(142, 11, 33, .55);
}}
.pm-hero::after {{
  content: "🦊"; position: absolute; right: -.4rem; bottom: -1.6rem;
  font-size: 7.5rem; opacity: .18; transform: rotate(-12deg);
}}
.pm-hero .pm-kicker {{
  text-transform: uppercase; letter-spacing: .14em; font-size: .72rem;
  font-weight: 700; opacity: .85;
}}
.pm-hero h1 {{ color: #fff; font-size: 2.4rem; font-weight: 800; margin: .15rem 0 .35rem; padding: 0; }}
.pm-hero p {{ margin: 0; max-width: 32rem; font-size: 1.02rem; opacity: .95; }}
.pm-how {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; position: relative; z-index: 1; }}
.pm-how span {{
  background: rgba(255, 255, 255, .16); border: 1px solid rgba(255, 255, 255, .28);
  border-radius: 999px; padding: .25rem .75rem; font-size: .85rem; font-weight: 600;
}}
.pm-legend {{ display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; font-size: .85rem; opacity: .8; margin: .2rem 0 .6rem; }}
.pm-step {{ display: flex; align-items: center; gap: .7rem; margin: 1.6rem 0 .2rem; }}
.pm-step .pm-num {{
  flex: none; width: 2rem; height: 2rem; border-radius: 50%;
  background: {MARIST_RED}; color: #fff; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}}
.pm-step .pm-title {{ font-size: 1.35rem; font-weight: 800; }}
.pm-pill {{
  display: inline-block; background: {MARIST_RED}; color: #fff; font-size: .7rem;
  font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  padding: .15rem .55rem; border-radius: 999px; margin-left: .4rem; vertical-align: middle;
}}
[class*="st-key-card-top"] {{
  border-left: 5px solid {MARIST_RED} !important;
  background: linear-gradient(90deg, rgba(200, 16, 46, .06), transparent 40%);
}}
.pm-footer {{ text-align: center; font-size: .8rem; opacity: .7; margin-top: .5rem; }}
</style>
"""
st.html(STYLE)


# --------------------------------------------------------------------------- helpers

@st.cache_data(show_spinner=False)
def load(path: str, modified: float, synthetic: bool) -> ImportResult:
    # `modified` is only part of the cache key, so editing the file reloads it.
    return load_professor_responses(path, synthetic=synthetic)


def md_escape(text: str) -> str:
    """Show instructor-supplied text literally instead of as Markdown formatting."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~])", r"\\\1", text)


def reset_answers() -> None:
    for d in DIMENSIONS:
        st.session_state[f"pref_{d}"] = NO_PREFERENCE
        st.session_state[f"imp_{d}"] = 1


def load_example(key: str) -> None:
    example = DEMO_STUDENTS[key]
    for d in DIMENSIONS:
        st.session_state[f"pref_{d}"] = example.values[d] or NO_PREFERENCE
        st.session_state[f"imp_{d}"] = example.weights[d] or 1


def step(number: int, title: str) -> None:
    st.markdown(
        f'<div class="pm-step"><span class="pm-num">{number}</span>'
        f'<span class="pm-title">{html.escape(title)}</span></div>',
        unsafe_allow_html=True,
    )


def question_help(dimension: str) -> str:
    anchors = SCALE_ANCHORS[dimension]
    return (f"**1** = {anchors[1]}  \n**3** = {anchors[3]}  \n**5** = {anchors[5]}\n\n"
            "2 and 4 are in between. Neither end is better; it's about what suits you.")


def render_side_by_side(group: tuple[ProfessorEntry, ...], expanded: bool) -> None:
    with st.expander("All instructors' answers side by side (no personalization)", expanded=expanded):
        rows = []
        for e in group:
            row = {"Instructor": e.name, "Section(s)": e.sections or "—"}
            for d in DIMENSIONS:
                value = e.profile.values[d]
                row[DIMENSION_LABELS[d].capitalize()] = "Unknown / not sure" if value is None else describe_value(d, value)
            rows.append(row)
        st.dataframe(rows, hide_index=True)
        st.caption(f"Source: {group[0].profile.source}.")


def render_card(result: MatchResult, entry: ProfessorEntry, rank: int | None) -> None:
    exp = explain(result)
    top = rank == 1
    key = re.sub(r"[^A-Za-z0-9_-]", "-", result.section_id)
    with st.container(border=True, key=f"card-{'top-' if top else ''}{key}"):
        left, right = st.columns([3, 1])
        with left:
            title = f"#{rank} · {entry.name}" if rank is not None else entry.name
            pill = '<span class="pm-pill">🦊 Top match</span>' if top else ""
            st.markdown(f"**{md_escape(title)}**{pill}", unsafe_allow_html=True)
            meta = [entry.course, entry.term] + ([f"Section(s) {entry.sections}"] if entry.sections else [])
            st.caption(md_escape(" · ".join(meta)))
        with right:
            if result.display_score is not None:
                label = "Alignment" if result.eligible_for_ranking else "Partial (not ranked)"
                st.metric(label, f"{result.display_score}/100")
        if result.display_score is not None and result.eligible_for_ranking:
            st.progress(result.display_score / 100)
        if result.eligible_for_ranking:
            # The score is already shown as the big number; don't repeat it in a sentence.
            st.caption("This instructor answered every question you rated.")
        else:
            st.write(exp.headline)
        for reason in exp.reasons:
            st.markdown(f"✅ {reason}")
        if result.alignment is not None and not exp.reasons:
            st.markdown(f"➖ {NO_CLOSE_MATCH}")
        if exp.tradeoff:
            st.markdown(f"⚠️ {exp.tradeoff}")
        for line in exp.missing:
            st.markdown(f"❔ {line}")
        with st.expander("Why this result?"):
            for line in exp.details:
                st.markdown(f"- {line}")
            if entry.note:
                st.markdown(f"**Instructor's note:** {md_escape(entry.note)}")
            for caveat in exp.caveats:
                st.caption(caveat)


# --------------------------------------------------------------------------- data

for d in DIMENSIONS:
    st.session_state.setdefault(f"pref_{d}", NO_PREFERENCE)
    st.session_state.setdefault(f"imp_{d}", 1)

with st.sidebar:
    st.header("Data")
    if PILOT_FILE.exists():
        data_mode = st.radio("Which data?", [PILOT, DEMO], key="data_mode")
    else:
        data_mode = DEMO
        st.caption("Showing synthetic demo data. Pilot data appears here once "
                   "data/private/professor_responses.csv exists.")

data_file = PILOT_FILE if data_mode == PILOT else DEMO_FILE
synthetic = data_mode == DEMO

try:
    result = load(str(data_file), data_file.stat().st_mtime, synthetic)
except (FormImportError, ValidationError, OSError, UnicodeDecodeError) as error:
    st.error(f"Could not load {data_file.name}: {error}")
    st.stop()

audit = result.audit
with st.sidebar:
    st.write(f"{audit.loaded} instructor responses loaded from {audit.rows_read} rows of {audit.file_name}.")
    with st.expander("Data status"):
        if not audit.excluded and not audit.replaced:
            st.write("Every row was loaded.")
        for row, reason in audit.excluded:
            st.write(f"Row {row} skipped: {reason}.")
        for earlier, later in audit.replaced:
            st.write(f"Row {earlier} replaced by the newer response in row {later}.")
        st.caption(f"File fingerprint (SHA-256): {audit.file_sha256[:16]}…")
    if synthetic:
        st.divider()
        st.subheader("Try an example")
        st.button("Example student 1", on_click=load_example, args=("1",), use_container_width=True)
        st.button("Example student 2", on_click=load_example, args=("2",), use_container_width=True)
    st.divider()
    st.caption("Nothing you enter on this page is saved.")


# --------------------------------------------------------------------------- page

st.html(
    '<div class="pm-hero"><div class="pm-kicker">Marist Red Foxes · Course planning</div>'
    "<h1>Prof-Match</h1>"
    "<p>Compare sections of the same course by how they're taught, "
    "and see the tradeoffs before you register.</p>"
    '<div class="pm-how"><span>① Pick your course</span><span>② Tell us how you like to learn</span>'
    "<span>③ See your best fits</span></div></div>"
)
if synthetic:
    st.warning("**Synthetic demo.** Every instructor and answer here is fictional, for demonstration only.", icon="🧪")
else:
    st.info("**Pilot data.** Instructor answers are self-reported through the Prof-Match form "
            "and shown with their permission.", icon="📋")

groups = group_by_course(result.entries)
if not groups:
    st.error("No instructor responses could be loaded. Check 'Data status' in the sidebar.")
    st.stop()

step(1, "Choose a course")
if st.session_state.get("course") not in groups:
    st.session_state.pop("course", None)
course = st.selectbox(
    "Course and term", options=list(groups), format_func=lambda key: group_label(groups[key]), key="course"
)
group = groups[course]
st.caption(f"{len(group)} instructor(s) answered for this course. "
           "Prerequisites, seats and registration eligibility are not checked.")

step(2, "What matters to you?")
st.caption("Answer only what you care about and leave the rest as 'No preference'. "
           "Hover the ? next to a question to see what the numbers mean.")
for d in DIMENSIONS:
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            st.selectbox(
                DIMENSION_QUESTIONS[d],
                options=[NO_PREFERENCE, 1, 2, 3, 4, 5],
                format_func=lambda v, d=d: "No preference" if v == NO_PREFERENCE else describe_value(d, v),
                key=f"pref_{d}",
                help=question_help(d),
            )
        with right:
            if st.session_state[f"pref_{d}"] != NO_PREFERENCE:
                st.selectbox(
                    "How important is this to you?",
                    options=[1, 2, 3],
                    format_func=lambda w: IMPORTANCE_LABELS[w].capitalize(),
                    key=f"imp_{d}",
                    help="Very important questions count three times as much as slightly important ones.",
                )
            else:
                st.caption("Pick an answer to include this in your comparison.")
values = {d: st.session_state[f"pref_{d}"] or None for d in DIMENSIONS}
answered = sum(v is not None for v in values.values())
left, right = st.columns([3, 1], vertical_alignment="center")
with left:
    st.progress(answered / len(DIMENSIONS), text=f"{answered} of {len(DIMENSIONS)} questions answered")
with right:
    st.button("Clear my answers", on_click=reset_answers, use_container_width=True)

weights = {d: 0 if values[d] is None else st.session_state[f"imp_{d}"] for d in DIMENSIONS}
prefs = StudentPreferences(values, weights)

step(3, "Your comparison")
comparison = compare_sections(prefs, [e.profile for e in group])
entry_for = {e.profile.section_id: e for e in group}

if comparison.mode == MODE_NO_PREFERENCES:
    st.info("Answer at least one question above to see alignment scores. "
            "Until then, here is every instructor's answers side by side.")
    if synthetic:
        st.write("**Not sure where to start?** Load an example student to see how it works:")
        one, two = st.columns(2)
        one.button("🦊 Try example student 1", on_click=load_example, args=("1",),
                   key="main_example_1", use_container_width=True)
        two.button("🦊 Try example student 2", on_click=load_example, args=("2",),
                   key="main_example_2", use_container_width=True)
    render_side_by_side(group, expanded=True)
else:
    if comparison.mode == MODE_RANKED:
        best = [r for r in comparison.ranked if r.rank == 1]
        names = " and ".join(f"**{md_escape(entry_for[r.result.section_id].name)}**" for r in best)
        st.success(f"Your best fit: {names} with {best[0].result.display_score}/100 alignment. "
                   "Details for every instructor are below.", icon="🦊")
        st.caption("Closest alignment with your answers first. 100 means the instructor teaches exactly "
                   "the way you said you prefer. Equal displayed scores share a rank.")
        st.html('<div class="pm-legend"><span>✅ close to what you want</span>'
                "<span>⚠️ a tradeoff to know about</span><span>❔ instructor didn't say</span></div>")
    elif comparison.mode == MODE_SINGLE_OPTION:
        st.info("Only one instructor has information on everything you rated, so there is nothing to rank it against.")
    elif comparison.mode == MODE_UNRANKED_INCOMPLETE:
        st.warning("No instructor has information on everything you rated, so nothing is ranked. "
                   "See what's missing below, or set a question to 'No preference'.")
    for ranked in comparison.ranked:
        rank = ranked.rank if comparison.mode == MODE_RANKED else None
        render_card(ranked.result, entry_for[ranked.result.section_id], rank)
    if comparison.needs_more_info:
        st.markdown("#### More information needed")
        st.caption("These instructors left one or more of your rated questions unanswered, "
                   "so they can't be compared fairly with fully answered ones.")
        for r in comparison.needs_more_info:
            render_card(r, entry_for[r.section_id], None)
    render_side_by_side(group, expanded=False)

st.divider()
st.caption(f"{NOT_A_PREDICTION} Method version {comparison.method_version}.")
st.html('<div class="pm-footer">🦊 Go Red Foxes! · An unofficial student project, '
        "not affiliated with or endorsed by Marist University.</div>")
