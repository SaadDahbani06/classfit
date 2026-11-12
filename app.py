"""ClassFit website (working name). Run with:  streamlit run app.py

This file only collects input and displays results. Every score and every
sentence of explanation comes from the profmatch package, so the website can
never disagree with the tested engine. Student answers live only in Streamlit's
per-session memory; this app never writes them to a file or database.

Design: Marist red on deep maroon. A landing hero states the idea; a demo
click collapses it so the ranked results fill the screen. Interactive parts are Streamlit
widgets restyled with CSS; static parts and charts are HTML built from escaped text.
"""

from __future__ import annotations

import base64
import re
import sys
from fractions import Fraction
from html import escape
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
# Find the profmatch package in src/ even if `pip install -r requirements.txt` was skipped.
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from profmatch.branding import PRODUCT_NAME, TAGLINE
from profmatch.explanations import CLOSE_MAX_GAP, NOT_A_PREDICTION, Explanation, explain, short_value
from profmatch.forms import (
    FormImportError,
    ImportResult,
    ProfessorEntry,
    group_by_course,
    group_label,
    load_professor_responses,
)
from profmatch.matching import (
    METHOD_VERSION,
    MODE_NO_PREFERENCES,
    MODE_RANKED,
    MODE_SINGLE_OPTION,
    MODE_UNRANKED_INCOMPLETE,
    NOT_REQUESTED,
    SCORED,
    Comparison,
    DimensionResult,
    MatchResult,
    compare_sections,
)
from profmatch.models import StudentPreferences
from profmatch.scale import (
    DIMENSIONS,
    IMPORTANCE_LABELS,
    NO_PREFERENCE_LABEL,
    QUESTION_BY_KEY,
    QUESTIONNAIRE_VERSION,
    QUESTIONS,
    SCALE_SPAN,
    UNKNOWN_ANSWER_LABEL,
    Question,
)
from profmatch.synthetic import DEMO_STUDENT_SUMMARIES, DEMO_STUDENTS
from profmatch.validation import ValidationError

DEMO_FILE = ROOT / "data" / "demo" / "professor_responses_demo.csv"
PILOT_FILE = ROOT / "data" / "private" / "professor_responses.csv"
DEMO, PILOT = "Synthetic demo", "Pilot data"
NO_PREFERENCE = 0       # answer value meaning "No preference"
DEFAULT_IMPORTANCE = 2  # "Important": the middle, so students can move either way
QUESTION_GROUPS = (("In class", ("discussion", "practice", "plan", "balance")),
                   ("Grading", ("exams", "collaboration")))

PRIVACY_SHORT = "Used only to show your results in this session; never written to a file or database."
PRIVACY_FULL = (f"{PRODUCT_NAME} uses your answers only to show your results. They are kept in the server's "
                "memory for this browser session and never written to a file or database. Usage statistics are "
                "turned off. If the site is hosted online, the hosting service may keep standard access logs, "
                "such as IP addresses.")

# An original fox mark (assets/classfit-fox.svg), not an official Marist logo. st.html strips inline
# SVG, so it is embedded as an image; alt="" because it is decorative next to the product name.
FOX = ('<img class="cf-fox" alt="" src="data:image/svg+xml;base64,'
       + base64.b64encode((ROOT / "assets" / "classfit-fox.svg").read_bytes()).decode() + '">')

st.set_page_config(page_title=f"{PRODUCT_NAME} · Red Foxes", page_icon=str(ROOT / "assets" / "classfit-fox.png"),
                   layout="wide", initial_sidebar_state="collapsed")

# Students never see data-source or import details; organizers add ?admin=1 to the address.
# This only hides clutter. It is not a security boundary, and nothing it reveals is private.
ORGANIZER = st.query_params.get("admin", "").lower() in ("1", "true", "yes")

STYLE = """
<style>
/* Escaped on purpose: the sanitizer behind st.html deletes a style block with anything tag-like in it. */
@property --p { syntax: "\\3c number\\3e "; inherits: false; initial-value: 0; }
:root {
  --cf-accent: #C8102E; --cf-accent-hover: #A00D25; --cf-accent-soft: #FDEEF1; --cf-maroon: #2A0A10; --cf-night: #190408;
  --cf-coral: #FF5A6E; --cf-text: #1F1A1C; --cf-muted: #625A5D; --cf-line: #E7E0DC; --cf-control: #A79E9A;
  --cf-page: #FBF8F6; --cf-gray: #F4EFEC; --cf-track: #EEE8E4; --cf-bar: #4A4346; --cf-hero-muted: #E8CCD4;
  --cf-display: "Bricolage Grotesque", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
}
[data-testid="stMainBlockContainer"] { max-width: 1320px; padding: 1.25rem 2rem 3rem; }
[data-testid="stHeader"] { background: transparent; height: 2rem; }
[data-testid="stStatusWidget"] { display: none; }
/* No grey flash while a click re-runs the page: the results should just change. */
[data-stale="true"], .stale-element { opacity: 1 !important; }

/* Landing hero */
.st-key-hero { background: radial-gradient(70% 90% at 8% 0%, #7E0A1D 0%, transparent 62%),
  radial-gradient(60% 90% at 100% 100%, #5C0716 0%, transparent 65%), var(--cf-night);
  border-radius: 24px; padding: clamp(24px, 4.4vh, 44px) 48px; box-shadow: 0 24px 60px -28px rgba(42, 10, 16, .65); }
.cf-eyebrow { color: var(--cf-hero-muted); font-size: .8125rem; font-weight: 650; letter-spacing: .1em;
  text-transform: uppercase; line-height: 1.5; margin: 0; }
.cf-hero { text-align: center; }
.cf-wordmark { display: flex; align-items: center; justify-content: center; gap: 12px; margin: 18px 0 0; }
.cf-wordmark .cf-fox { width: 44px; height: 44px; flex: none; filter: drop-shadow(0 2px 10px rgba(255, 90, 110, .45)); }
.cf-hero h1 { color: #fff; font-family: var(--cf-display); font-size: 1.875rem; font-weight: 700; line-height: 1.1;
  letter-spacing: -.02em; margin: 0; padding: 0; }
.cf-tagline { color: #fff; font-family: var(--cf-display); font-size: clamp(2.5rem, min(4.5vw, 9vh), 4.75rem); font-weight: 800; text-wrap: balance;
  line-height: 1.02; letter-spacing: -.035em; margin: 22px 0 0; }
.cf-tagline em { display: block; font-style: normal; color: var(--cf-coral); }
.cf-description { color: var(--cf-hero-muted); font-size: 1.0625rem; line-height: 1.55; max-width: 640px; margin: 18px auto 8px; }
.st-key-hero-examples { max-width: 720px; margin: 0 auto; width: 100%; }
.cf-cta-note { color: var(--cf-hero-muted); font-size: .8125rem; line-height: 1.5; margin: 0; text-align: center; }
.st-key-hero button[kind="primary"] { min-height: 52px; background: var(--cf-accent); border: 1px solid var(--cf-coral);
  border-radius: 12px; box-shadow: 0 10px 28px -10px rgba(255, 90, 110, .8); transition: transform 120ms ease, background-color 120ms ease; }
.st-key-hero button[kind="primary"] p { font-size: 1rem; font-weight: 700; color: #fff; }
.st-key-hero button[kind="primary"]:hover { background: var(--cf-coral); transform: translateY(-1px); }

/* Slim header once a demo is running, so the results get the screen */
.cf-topbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; background: var(--cf-night);
  border-radius: 14px; padding: 12px 20px; color: #fff; }
.cf-topbar .cf-fox { width: 30px; height: 30px; flex: none; }
.cf-topbar h1 { color: #fff; font-family: var(--cf-display); font-size: 1.375rem; font-weight: 750; letter-spacing: -.02em;
  margin: 0 0 0 -6px; padding: 0; line-height: 1.2; }
.cf-topbar p { color: var(--cf-hero-muted); font-size: .9375rem; margin: 0; }
.st-key-example-strip { background: #fff; border: 1px solid var(--cf-line); border-radius: 14px; padding: 12px 16px 12px 20px; }
.cf-example { font-size: .9375rem; line-height: 1.5; color: var(--cf-text); margin: 0; }
.cf-example strong { font-weight: 700; color: var(--cf-accent); }

/* Notices and plain text blocks */
.cf-notice { background: var(--cf-gray); border-radius: 10px; padding: 12px 16px; font-size: .875rem; line-height: 1.55;
  color: var(--cf-text); margin: 0; }
.cf-data-notice { background: transparent; padding: 2px 4px; color: var(--cf-muted); text-align: center; font-size: .8125rem; }
.cf-small { font-size: .875rem; line-height: 1.55; color: var(--cf-muted); margin: 0; }
.cf-intro { font-size: .9375rem; line-height: 1.55; color: var(--cf-muted); margin: 0; }
.cf-empty { background: #fff; border: 1.5px dashed var(--cf-control); border-radius: 16px; padding: 32px 28px; text-align: center; }
.cf-empty strong { display: block; font-family: var(--cf-display); font-size: 1.375rem; font-weight: 750;
  letter-spacing: -.02em; color: var(--cf-text); margin-bottom: 6px; }

/* Headings */
h2.cf-step { display: flex; align-items: center; gap: 10px; margin: 8px 0 0; padding: 0; font-family: var(--cf-display);
  font-size: 1.5rem; font-weight: 750; line-height: 1.2; letter-spacing: -.025em; color: var(--cf-text); }
h2.cf-step .cf-n { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; flex: none;
  border-radius: 50%; background: var(--cf-accent); color: #fff; font-family: inherit; font-size: .9375rem; font-weight: 750; letter-spacing: 0; }
h3.cf-group { font-size: .8125rem; font-weight: 700; letter-spacing: .09em; text-transform: uppercase;
  color: var(--cf-accent); margin: 10px 0 0; padding: 0; }
h3.cf-more { font-family: var(--cf-display); font-size: 1.25rem; font-weight: 750; letter-spacing: -.02em; line-height: 1.25;
  margin: 12px 0 0; padding: 0; color: var(--cf-text); }
.cf-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* Two panes: answer on the left, results stay in view on the right */
@media (min-width: 1000px) {
  [data-testid="stColumn"]:has([class*="st-key-results-pane"]) { position: sticky; top: 12px; align-self: flex-start;
    max-height: calc(100vh - 24px); overflow-y: auto; scrollbar-width: thin; padding: 0 6px 12px 2px; }
  /* Room below the questions, or the footer pushes the pinned results up off the top of the screen. */
  .st-key-answers-pane { padding-bottom: 170px; }
}
@media (max-width: 999px) {
  .st-key-workspace > div > [data-testid="stHorizontalBlock"], .st-key-workspace > [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  [data-testid="stColumn"]:has([class*="st-key-results-pane"]), [data-testid="stColumn"]:has(.st-key-answers-pane) { flex: 1 1 100%; width: 100%; min-width: 100%; }
  [data-testid="stColumn"]:has(.st-key-results-pane-first) { order: -1; }
}

/* Question cards */
[class*="st-key-q-"] { background: #fff; border: 1px solid var(--cf-line); border-radius: 14px; padding: 16px 18px; gap: 10px; }
[class*="st-key-pref_"] [data-testid="stWidgetLabel"] p { font-size: 1rem; font-weight: 650; line-height: 1.4; color: var(--cf-text); }
[class*="st-key-imp_"] [data-testid="stWidgetLabel"] p { font-size: .8125rem; font-weight: 600; color: var(--cf-muted); }
.cf-def { font-size: .8125rem; line-height: 1.5; color: var(--cf-muted); margin: 0; }
.cf-chosen { font-size: .8125rem; line-height: 1.5; color: var(--cf-text); margin: 4px 0 0; }
.cf-chosen strong { font-weight: 650; }

/* Answer and importance pills */
[data-testid="stButtonGroup"] [role="radiogroup"] { gap: 6px; flex-wrap: wrap; }
button[data-variant="pills"] { min-height: 38px; padding: 6px 12px; border: 1px solid var(--cf-control); border-radius: 999px;
  background: #fff; color: var(--cf-text); transition: background-color 120ms ease, border-color 120ms ease; }
button[data-variant="pills"] p { font-size: .8125rem; line-height: 1.3; }
button[data-variant="pills"]:hover { background: var(--cf-accent-soft); border-color: var(--cf-accent); color: var(--cf-text); }
button[data-variant="pills"]:focus-visible { outline: 3px solid var(--cf-maroon); outline-offset: 3px; }
[class*="st-key-pref_"] button[data-variant="pills"][aria-checked="true"] { background: var(--cf-accent);
  border-color: var(--cf-accent); color: #fff; }
[class*="st-key-pref_"] button[data-variant="pills"][aria-checked="true"] p { color: #fff; font-weight: 700; }
[class*="st-key-pref_"] button[data-variant="pills"][aria-checked="true"]:hover { background: var(--cf-accent-hover);
  border-color: var(--cf-accent-hover); }
[class*="st-key-imp_"] button[data-variant="pills"][aria-checked="true"] { background: var(--cf-maroon);
  border-color: var(--cf-maroon); color: #fff; }
[class*="st-key-imp_"] button[data-variant="pills"][aria-checked="true"] p { color: #fff; font-weight: 700; }

/* Buttons and dropdown */
button[kind="secondary"] { min-height: 44px; border: 1px solid var(--cf-control); border-radius: 10px; background: #fff; color: var(--cf-text); }
button[kind="secondary"] p { font-size: .875rem; font-weight: 600; }
button[kind="secondary"]:hover { background: var(--cf-gray); border-color: var(--cf-text); color: var(--cf-text); }
button[kind="secondary"]:focus-visible, button[kind="primary"]:focus-visible { outline: 3px solid var(--cf-maroon); outline-offset: 3px; }
.st-key-example-strip button[kind="primary"] { min-height: 44px; background: var(--cf-accent); border: 0; border-radius: 10px; }
.st-key-example-strip button[kind="primary"] p { font-size: .9375rem; font-weight: 700; color: #fff; }
.st-key-example-strip button[kind="primary"]:hover { background: var(--cf-accent-hover); }
[data-testid="stSidebar"] button[kind="primary"] { min-height: 44px; background: var(--cf-accent-soft);
  border: 1px solid var(--cf-accent); border-radius: 10px; color: var(--cf-maroon); }
[data-testid="stSidebar"] button[kind="primary"] p { font-size: .875rem; font-weight: 750; color: var(--cf-maroon); }
[data-testid="stSelectbox"] [role="group"] { min-height: 48px; background: #fff; border-color: var(--cf-control); }

/* Progress */
.cf-progress-label { font-size: .8125rem; font-weight: 600; color: var(--cf-muted); margin: 0 0 8px; }
progress.cf-bar { appearance: none; -webkit-appearance: none; display: block; width: 100%; height: 8px; border: 0;
  border-radius: 999px; background: var(--cf-track); overflow: hidden; color: var(--cf-accent); margin: 0; }
progress.cf-bar::-webkit-progress-bar { background: var(--cf-track); border-radius: 999px; }
progress.cf-bar::-webkit-progress-value { background: var(--cf-accent); border-radius: 999px; transition: width 300ms ease; }
progress.cf-bar::-moz-progress-bar { background: var(--cf-accent); border-radius: 999px; }

/* Score ring */
.cf-ring { --size: 76px; --ring: var(--cf-bar); --ring-track: var(--cf-track); --ring-face: #fff; position: relative; flex: none;
  width: var(--size); height: var(--size); border-radius: 50%; display: grid; place-items: center;
  background: conic-gradient(var(--ring) calc(var(--p) * 1%), var(--ring-track) 0); animation: cf-sweep 800ms cubic-bezier(.2, .8, .2, 1) backwards; }
.cf-ring::before { content: ""; position: absolute; inset: 7px; border-radius: 50%; background: var(--ring-face); }
.cf-ring span { position: relative; font-family: var(--cf-display); font-size: 1.625rem; font-weight: 800; letter-spacing: -.03em;
  color: var(--cf-text); font-variant-numeric: tabular-nums; }
.cf-ring.cf-ring-top { --ring: var(--cf-accent); }
.cf-ring.cf-ring-hero { --size: 128px; --ring: var(--cf-coral); --ring-track: rgba(255, 255, 255, .14); --ring-face: var(--cf-night); }
.cf-ring.cf-ring-hero::before { inset: 11px; }
.cf-ring.cf-ring-hero span { color: #fff; font-size: 3rem; }

/* Results banner */
.cf-banner { background: radial-gradient(80% 110% at 0% 0%, #6A0918 0%, transparent 65%), var(--cf-night);
  border-radius: 20px; padding: 24px 26px; color: #fff; box-shadow: 0 20px 44px -26px rgba(42, 10, 16, .75); }
.cf-banner-top { display: flex; align-items: center; gap: 22px; }
.cf-summary { color: #fff; font-size: 1rem; line-height: 1.3; margin: 0; }
.cf-summary strong { display: block; font-family: var(--cf-display); font-size: clamp(1.5rem, 2.2vw, 2rem); font-weight: 800;
  letter-spacing: -.03em; line-height: 1.1; margin-top: 6px; }
.cf-board { list-style: none; margin: 20px 0 0 !important; padding: 16px 0 0 !important; display: grid; gap: 8px;
  border-top: 1px solid rgba(255, 255, 255, .16); }
.cf-board li { display: grid; grid-template-columns: minmax(0, 11.5rem) minmax(0, 1fr) 2.25rem; align-items: center; gap: 12px;
  margin: 0; padding: 0; font-size: .875rem; color: var(--cf-hero-muted); }
.cf-board .cf-board-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cf-board .cf-board-track { height: 10px; border-radius: 999px; background: rgba(255, 255, 255, .1); overflow: hidden; }
.cf-board .cf-board-fill { display: block; height: 100%; width: var(--w); border-radius: 999px; background: rgba(255, 255, 255, .42);
  animation: cf-grow 800ms cubic-bezier(.2, .8, .2, 1) backwards; }
.cf-board .cf-board-score { text-align: right; font-weight: 700; color: #fff; font-variant-numeric: tabular-nums; }
.cf-board li.cf-board-top { color: #fff; font-weight: 700; }
.cf-board li.cf-board-top .cf-board-fill { background: var(--cf-coral); }
.cf-board li.cf-board-open { grid-template-columns: minmax(0, 11.5rem) minmax(0, 1fr); }
.cf-board li.cf-board-open .cf-board-why { font-size: .8125rem; border: 1px dashed rgba(255, 255, 255, .45); border-radius: 999px;
  padding: 2px 10px; justify-self: start; }

/* Chart legend */
.cf-legend { list-style: none; margin: 2px 0 !important; padding: 0 !important; display: flex; flex-wrap: wrap; gap: 6px 18px;
  font-size: .8125rem; color: var(--cf-muted); }
.cf-legend li { display: flex; gap: 7px; align-items: center; margin: 0; padding: 0; }
.cf-dot-you, .cf-dot-them { display: inline-block; width: 12px; height: 12px; border-radius: 50%; flex: none; }
.cf-dot-you { background: #fff; border: 2.5px solid var(--cf-text); }
.cf-dot-them { background: var(--cf-accent); box-shadow: 0 0 0 2px #fff; }

/* Result cards */
[class*="st-key-card-"] { border: 1px solid var(--cf-line); border-radius: 16px; padding: 20px 22px; background: #fff; gap: 8px; }
[class*="st-key-card-top-"] { border: 2px solid var(--cf-accent); box-shadow: 0 14px 34px -22px rgba(200, 16, 46, .6); }
[class*="st-key-card-unranked-"] { background: var(--cf-page); border: 1.5px dashed var(--cf-control); }
.cf-card-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.cf-name-line { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.cf-name { font-family: var(--cf-display); font-size: 1.25rem; font-weight: 750; line-height: 1.25; letter-spacing: -.02em;
  margin: 0; padding: 0; color: var(--cf-text); }
.cf-badge { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 999px; font-size: .75rem;
  font-weight: 700; white-space: nowrap; }
.cf-badge-closest { color: #fff; background: var(--cf-accent); }
.cf-badge-unranked { color: var(--cf-muted); background: var(--cf-track); }
.cf-meta { font-size: .8125rem; color: var(--cf-muted); margin: 4px 0 0; }
.cf-coverage { font-size: .8125rem; color: var(--cf-muted); margin: 10px 0 0; }
.cf-lead { font-size: .9375rem; line-height: 1.55; color: var(--cf-text); margin: 12px 0 0; }

/* You-versus-instructor chart: one five-step track per rated question */
.cf-tracks { list-style: none; margin: 14px 0 0 !important; padding: 0 !important; display: grid; gap: 4px; }
.cf-tracks li { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr) 4.25rem; align-items: center; gap: 14px;
  margin: 0; padding: 3px 0; font-size: .8125rem; color: var(--cf-text); }
.cf-track-name { line-height: 1.25; font-weight: 550; }
.cf-pips { display: inline-flex; gap: 2px; margin-left: 6px; vertical-align: 1px; }
.cf-pips i { width: 5px; height: 5px; border-radius: 50%; background: var(--cf-track); }
.cf-pips i.on { background: var(--cf-bar); }
.cf-track { position: relative; height: 18px; margin: 0 8px; }
.cf-track::before { content: ""; position: absolute; left: -8px; right: -8px; top: 8px; height: 2px; border-radius: 2px; background: var(--cf-track); }
.cf-track.cf-track-open::before { background: none; border-top: 2px dashed var(--cf-control); }
.cf-tick { position: absolute; top: 6px; width: 2px; height: 6px; margin-left: -1px; background: var(--cf-control); border-radius: 1px; }
.cf-gap-line { position: absolute; top: 7px; height: 4px; background: var(--cf-control); border-radius: 2px; }
.cf-gap-line.far { background: var(--cf-accent); opacity: .35; }
.cf-mark-you, .cf-mark-them { position: absolute; top: 9px; border-radius: 50%; transform: translate(-50%, -50%); transition: left 400ms ease; }
.cf-mark-them { width: 9px; height: 9px; background: var(--cf-accent); }
.cf-mark-you { width: 17px; height: 17px; background: #fff; border: 2.5px solid var(--cf-text); box-sizing: border-box; }
.cf-gap { text-align: right; font-size: .75rem; font-weight: 700; color: var(--cf-muted); white-space: nowrap; }
.cf-gap.same { color: var(--cf-text); }
.cf-gap.far { color: var(--cf-accent); }

/* Reasons */
.cf-why { margin: 12px 0 0; font-size: .875rem; }
.cf-why summary { cursor: pointer; font-weight: 650; color: var(--cf-muted); padding: 4px 0; }
.cf-why summary:hover { color: var(--cf-text); }
.cf-reasons { list-style: none; margin: 8px 0 0 !important; padding: 0 !important; display: grid; gap: 8px; }
.cf-reasons li { margin: 0; padding: 0; font-size: .875rem; line-height: 1.5; color: var(--cf-text); }
.cf-kind { display: inline-block; font-size: .75rem; font-weight: 700; line-height: 1.5; padding: 0 7px; border-radius: 999px;
  background: var(--cf-track); color: var(--cf-text); margin-right: 4px; vertical-align: 1px; }
.cf-kind-tradeoff { background: var(--cf-accent-soft); color: var(--cf-accent-hover); }
.cf-kind-missing { background: #fff; border: 1px dashed var(--cf-muted); }
.cf-note { margin: 12px 0 0; padding: 10px 14px; background: var(--cf-page); border-radius: 10px; font-size: .8125rem;
  line-height: 1.55; color: var(--cf-muted); }
[class*="st-key-card-unranked-"] .cf-note { background: #fff; }
.cf-note strong { color: var(--cf-text); font-weight: 600; }

/* Collapsible sections: open rows, not boxes */
[data-testid="stExpander"] details { border: 0; border-top: 1px solid var(--cf-line); border-radius: 0; background: transparent; }
[data-testid="stExpander"] summary { min-height: 40px; padding: 8px 4px; }
[data-testid="stExpander"] summary:hover { background: var(--cf-gray); }
[data-testid="stExpander"] summary p { font-size: .8125rem; font-weight: 600; }
.st-key-page-sections [data-testid="stExpander"] summary p { font-size: .9375rem; }

/* Footer */
.cf-footer { margin: 28px 0 0; border-top: 1px solid var(--cf-line); padding-top: 18px; font-size: .8125rem;
  line-height: 1.6; color: var(--cf-muted); }
.cf-footer p { margin: 0 0 6px; }

/* Sidebar */
.cf-side-eyebrow { display: flex; align-items: center; gap: 8px; color: var(--cf-accent); font-size: .8125rem;
  font-weight: 750; letter-spacing: .03em; margin: 0; }
.cf-side-eyebrow .cf-fox { width: 22px; height: 22px; flex: none; }
.cf-side-rule { display: block; width: 36px; height: 3px; background: var(--cf-accent); margin: 10px 0 0; }
.cf-side-h { font-size: 18px; font-weight: 700; line-height: 1.35; margin: 12px 0 0; padding: 0; color: var(--cf-text); }
.cf-side-p { font-size: .875rem; line-height: 1.6; color: var(--cf-muted); margin: 8px 0 0; }
.cf-side-result { font-size: .875rem; line-height: 1.6; color: var(--cf-text); margin: 8px 0 0; }

@keyframes cf-sweep { from { --p: 0; } }
@keyframes cf-grow { from { width: 0; } }

@media (min-width: 1700px) {
  [data-testid="stMainBlockContainer"] { max-width: 1560px; }
}
@media (max-width: 1420px) {
  [data-testid="stMainBlockContainer"] { padding-top: 2.5rem; }
}
@media (max-width: 999px) {
  .st-key-hero { padding: 28px 24px; border-radius: 18px; }
}
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 2.5rem 1rem 2rem; }
  .cf-board .cf-board-name { white-space: normal; line-height: 1.25; }
  .st-key-hero { padding: 24px 18px; }
  .cf-tagline { font-size: 2.5rem; }
  button[data-variant="pills"] { min-height: 44px; }
  .cf-banner { padding: 20px 18px; }
  .cf-banner-top { gap: 16px; }
  .cf-ring.cf-ring-hero { --size: 88px; }
  .cf-ring.cf-ring-hero::before { inset: 8px; }
  .cf-ring.cf-ring-hero span { font-size: 2rem; }
  .cf-board li { grid-template-columns: minmax(0, 7.5rem) minmax(0, 1fr) 2rem; gap: 8px; font-size: .8125rem; }
  .cf-board li.cf-board-open { grid-template-columns: minmax(0, 7.5rem) minmax(0, 1fr); }
  [class*="st-key-card-"] { padding: 16px; }
  .cf-tracks li { grid-template-columns: minmax(0, 1fr) 4rem; gap: 2px 10px; }
  .cf-track-name { grid-column: 1 / -1; }
  .cf-topbar p { font-size: .8125rem; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
"""
st.html(STYLE)


# --------------------------------------------------------------------------- helpers

@st.cache_data(show_spinner=False)
def load(path: str, modified: float, synthetic: bool) -> ImportResult:
    # `modified` is only part of the cache key, so editing the file reloads it.
    return load_professor_responses(path, synthetic=synthetic)


def md_escape(text: str) -> str:
    """Show instructor-supplied text literally instead of as Markdown, LaTeX ($...$)
    or Streamlit directive (:red[...]) formatting."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$:=])", r"\\\1", text)


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def join_names(names: list[str]) -> str:
    """['A'] -> 'A'; ['A', 'B', 'C'] -> 'A, B and C'."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def reset_answers() -> None:
    for d in DIMENSIONS:
        st.session_state[f"pref_{d}"] = NO_PREFERENCE
        st.session_state[f"imp_{d}"] = DEFAULT_IMPORTANCE
    st.session_state["compact"] = False  # back to the full landing hero


def load_example(key: str) -> None:
    example = DEMO_STUDENTS[key]
    for d in DIMENSIONS:
        st.session_state[f"pref_{d}"] = example.values[d] or NO_PREFERENCE
        st.session_state[f"imp_{d}"] = example.weights[d] or DEFAULT_IMPORTANCE
    # Only a demo click collapses the hero: doing it on a typed answer would move the page under the cursor.
    st.session_state["compact"] = True


def step(number: int, title: str) -> None:
    # A real heading, so screen readers can jump between the three steps.
    st.html(f'<h2 class="cf-step"><span class="cf-n" aria-hidden="true">{number}</span>'
            f'<span class="cf-hidden">Step {number}: </span>{escape(title)}</h2>')


def question_help(q: Question) -> str:
    answers = "  \n".join(f"**{i}** = {full}" for i, (_, full) in enumerate(q.answers, start=1))
    return f"{answers}\n\nNeither end is better; it's about what suits you in this course."


def render_question(q: Question) -> None:
    with st.container(key=f"q-{q.key}"):
        st.pills(
            q.student_question,
            options=[1, 2, 3, 4, 5, NO_PREFERENCE],
            format_func=lambda v, q=q: NO_PREFERENCE_LABEL if v == NO_PREFERENCE else q.answers[v - 1][0],
            key=f"pref_{q.key}",
            required=True,
            help=question_help(q),
        )
        value = st.session_state[f"pref_{q.key}"]
        chosen = ("No preference. This question isn't used in your comparison." if value == NO_PREFERENCE
                  else f"{q.answers[value - 1][1]}.")
        st.html(f'<p class="cf-def">{escape(q.definition)}</p>'
                f'<p class="cf-chosen"><strong>You chose:</strong> {escape(chosen)}</p>')
        if value != NO_PREFERENCE:
            st.pills(
                "How important is this to you?",
                options=[1, 2, 3],
                format_func=lambda w: IMPORTANCE_LABELS[w].capitalize(),
                key=f"imp_{q.key}",
                required=True,
                help="Very important counts three times as much as slightly important.",
            )


def closest(comparison: Comparison, entry_for: dict[str, ProfessorEntry]) -> tuple[str, int, bool]:
    """('Instructor A and Instructor C', 100, True): who shares rank 1, their score, and whether it's a tie."""
    top = [r.result for r in comparison.ranked if r.rank == 1]
    return join_names([entry_for[r.section_id].name for r in top]), top[0].display_score, len(top) > 1


def demo_outcome(key: str, group: tuple[ProfessorEntry, ...], entry_for: dict[str, ProfessorEntry]) -> str:
    comparison = compare_sections(DEMO_STUDENTS[key], [e.profile for e in group])
    course = group_label(group)
    if comparison.mode == MODE_RANKED:
        names, score, tied = closest(comparison, entry_for)
        return f"Closest match in {course}: {names}, {'tied at' if tied else 'at'} {score}/100."
    if comparison.mode == MODE_SINGLE_OPTION:
        only = comparison.ranked[0].result
        return (f"In {course}, only {entry_for[only.section_id].name} answered everything this student rated "
                f"({only.display_score}/100).")
    return f"In {course}, no instructor answered everything this student rated."


def render_side_by_side(group: tuple[ProfessorEntry, ...]) -> None:
    with st.expander("All instructors' answers side by side"):
        rows = []
        for e in group:
            row = {"Instructor": e.name, "Section(s)": e.sections or "—"}
            for q in QUESTIONS:
                value = e.profile.values[q.key]
                row[q.topic] = UNKNOWN_ANSWER_LABEL if value is None else short_value(q.key, value)
            rows.append(row)
        st.dataframe(rows, hide_index=True)
        st.caption(md_escape(f"Source: {group[0].profile.source}. Hover over a question's ? for what each "
                             "answer means."))


def ring_html(score: int, kind: str, label: bool = True) -> str:
    aria = f'role="img" aria-label="Alignment {score}/100"' if label else 'aria-hidden="true"'
    return f'<div class="cf-ring {kind}" style="--p:{score}" {aria}><span>{score}</span></div>'


def leaderboard_html(comparison: Comparison, entry_for: dict[str, ProfessorEntry]) -> str:
    """Every instructor at a glance: ranked bars, then anyone who can't be ranked (never given a guessed score)."""
    rows = []
    for ranked in comparison.ranked:
        score = ranked.result.display_score
        name = escape(entry_for[ranked.result.section_id].name)
        rows.append(f'<li class="{"cf-board-top" if ranked.rank == 1 else ""}" title="{name}: {score} out of 100">'
                    f'<span class="cf-board-name">{name}</span><span class="cf-board-track">'
                    f'<span class="cf-board-fill" style="--w:{score}%"></span></span>'
                    f'<span class="cf-board-score">{score}</span></li>')
    for r in comparison.needs_more_info:
        name = escape(entry_for[r.section_id].name)
        rows.append(f'<li class="cf-board-open"><span class="cf-board-name">{name}</span>'
                    '<span class="cf-board-why">Not ranked: missing an answer, never guessed</span></li>')
    return f'<ol class="cf-board" aria-label="All instructors in order">{"".join(rows)}</ol>'


def position(value: int | float | Fraction) -> str:
    """Where an answer sits along a track: 1 -> '0%', 5 -> '100%'."""
    return f"{float((Fraction(value) - 1) / SCALE_SPAN * 100):g}%"


def track_row(d: DimensionResult) -> str:
    """One question: where the student's answer and the instructor's answer sit on the five steps."""
    q = QUESTION_BY_KEY[d.dimension]
    ticks = "".join(f'<span class="cf-tick" style="left:{i * 25}%"></span>' for i in range(5))
    you = f'<span class="cf-mark-you" style="left:{position(d.preference)}"></span>'
    pips = "".join(f'<i class="{"on" if i < d.weight else ""}"></i>' for i in range(3))
    if d.status == SCORED:
        gap = abs(Fraction(d.preference) - Fraction(d.observed))
        far = gap > CLOSE_MAX_GAP
        low = min(Fraction(d.preference), Fraction(d.observed))
        link = (f'<span class="cf-gap-line{" far" if far else ""}" style="left:{position(low)};'
                f'width:{float(gap / SCALE_SPAN * 100):g}%"></span>')
        them = f'<span class="cf-mark-them" style="left:{position(d.observed)}"></span>'
        gap_text = "Same" if gap == 0 else f"{float(gap):g} step{'' if gap == 1 else 's'}"
        gap_class = "same" if gap == 0 else "far" if far else ""
        track_class, theirs = "", short_value(d.dimension, d.observed)
    else:
        link, them, gap_text, gap_class = "", "", "No answer", ""
        track_class, theirs = " cf-track-open", UNKNOWN_ANSWER_LABEL
    said = f"You: {short_value(d.dimension, d.preference)}. Instructor: {theirs}."
    return (f'<li title="{escape(said)}"><span class="cf-track-name">{escape(q.topic)}'
            f'<span class="cf-pips" title="You rated this {IMPORTANCE_LABELS[d.weight]}" aria-hidden="true">{pips}</span></span>'
            f'<span class="cf-track{track_class}" role="img" aria-label="{escape(said)}">{ticks}{link}{you}{them}</span>'
            f'<span class="cf-gap {gap_class}">{gap_text}</span></li>')


def card_html(result: MatchResult, entry: ProfessorEntry, rank: int | None, exp: Explanation) -> str:
    """The static part of a result card: heading, score ring, answer chart, reasons and the instructor's note."""
    top = rank == 1
    title = f"#{rank} · {entry.name}" if rank is not None else entry.name
    meta = " · ".join([entry.course, entry.term] + ([f"Section(s) {entry.sections}"] if entry.sections else []))
    heading = "h3" if result.eligible_for_ranking else "h4"  # unranked cards sit under "More information needed"
    badge = '<span class="cf-badge cf-badge-closest">Closest match</span>' if top else ""
    if result.eligible_for_ranking:
        side = ring_html(result.display_score, "cf-ring-top" if top else "")
        body = '<p class="cf-coverage">The instructor answered every question you rated.</p>'
    else:
        # A partial score is not comparable with full ones, so it only appears inside the sentence.
        side = '<span class="cf-badge cf-badge-unranked">Not ranked</span>'
        body = f'<p class="cf-lead">{escape(exp.headline)}</p>'
    tracks = "".join(track_row(d) for d in result.dimensions if d.status != NOT_REQUESTED)
    rows = ([("Close", "", line) for line in exp.reasons]
            + [("Tradeoff", " cf-kind-tradeoff", line) for line in exp.tradeoffs]
            + [("No answer", " cf-kind-missing", line) for line in exp.missing])
    reasons = "".join(f'<li><span class="cf-kind{cls}">{kind}</span> {escape(text)}</li>' for kind, cls, text in rows)
    # The closest match is open so its reasons are visible at once; the rest stay one click away.
    why = (f'<details class="cf-why"{" open" if top else ""}><summary>In words</summary>'
           f'<ul class="cf-reasons">{reasons}</ul></details>') if reasons else ""
    note = ('<p class="cf-note"><strong>Instructor&#x27;s note (not part of the score):</strong> '
            f"{escape(entry.note)}</p>") if entry.note else ""
    return (f'<div class="cf-card-head"><div><div class="cf-name-line"><{heading} class="cf-name">{escape(title)}'
            f'</{heading}>{badge}</div><p class="cf-meta">{escape(meta)}</p></div>{side}</div>'
            f'<ul class="cf-tracks">{tracks}</ul>{body}{why}{note}')


def render_card(result: MatchResult, entry: ProfessorEntry, rank: int | None) -> None:
    exp = explain(result)
    if not result.eligible_for_ranking:
        style = "unranked-"
    else:
        style = "top-" if rank == 1 else ""
    # Section IDs are unique within a comparison, so they make stable, collision-free keys.
    with st.container(key=f"card-{style}{result.section_id}"):
        st.html(card_html(result, entry, rank, exp))
        with st.expander("Why this result?"):
            for line in exp.details:
                st.markdown(f"- {line}")
            if exp.calculation:
                st.markdown(f"**{exp.calculation}**")
            for caveat in exp.caveats:
                st.caption(md_escape(caveat))


def render_method() -> None:
    even = [q for q in QUESTIONS if q.evenly_spaced]
    uneven = [f"'{q.topic}'" for q in QUESTIONS if not q.evenly_spaced]
    with st.expander("How the score works"):
        st.markdown(
            "For each question you answered, **similarity = 1 − (steps apart ÷ 4)**: the same answer "
            "scores 1 and opposite ends score 0.\n\n"
            "**Alignment = 100 × Σ(importance × similarity) ÷ Σ(importance)**, over the questions you answered "
            "that the instructor also answered. That equals 100 × [1 − Σ(importance × steps apart) ÷ "
            "(4 × Σ importance)].\n\n"
            "Counting steps treats neighbouring answers as equally far apart. That is a reasonable "
            f"approximation for the {len(even)} questions that use equal-width ranges, such as 0–20% and "
            f"21–40%. {join_names(uneven)} uses ordered descriptions whose real gaps are uneven, so distances "
            "there are a simplification.\n\n"
            f"If an instructor answered '{UNKNOWN_ANSWER_LABEL}', that question is left out for them (never "
            "guessed), and they are not ranked against instructors who answered everything you rated.\n\n"
            "Scores are rounded to whole numbers and equal rounded scores share a rank. Small differences can "
            "come from a single answer one step apart, so compare the reasons, not just the numbers.\n\n"
            f"{NOT_A_PREDICTION} It is a fixed, published formula, not machine learning or AI."
        )


# --------------------------------------------------------------------------- data

for d in DIMENSIONS:
    st.session_state.setdefault(f"pref_{d}", NO_PREFERENCE)
    st.session_state.setdefault(f"imp_{d}", DEFAULT_IMPORTANCE)

with st.sidebar:
    demo_slot = st.container()  # filled at the end, once the course is known
    technical = st.expander("Technical details") if ORGANIZER else None

# Real (pilot) data is shown whenever it exists; only organizers can switch back to the demo.
data_mode = PILOT if PILOT_FILE.exists() else DEMO
if technical is not None and PILOT_FILE.exists():
    with technical:
        data_mode = st.radio("Data source", [PILOT, DEMO], key="data_mode")

data_file = PILOT_FILE if data_mode == PILOT else DEMO_FILE
synthetic = data_mode == DEMO

try:
    result = load(str(data_file), data_file.stat().st_mtime, synthetic)
except (FormImportError, ValidationError, OSError, UnicodeDecodeError) as error:
    st.error(md_escape(f"Could not load {data_file.name}: {error}"))
    st.stop()

audit = result.audit
if technical is not None:
    with technical:
        st.write(f"{data_mode}: {plural(audit.loaded, 'instructor response')} loaded from "
                 f"{plural(audit.rows_read, 'row')} of {md_escape(audit.file_name)}.")
        if not audit.excluded and not audit.replaced:
            st.write("Every row was loaded.")
        for row, reason in audit.excluded:
            st.write(f"Row {row} skipped: {md_escape(reason)}.")
        for earlier, later in audit.replaced:
            st.write(f"Row {earlier} replaced by the newer response in row {later}.")
        if not PILOT_FILE.exists():
            st.caption("Pilot data appears here once `data/private/professor_responses.csv` exists.")
        st.caption(f"File fingerprint (SHA-256): {audit.file_sha256[:16]}…")
        st.caption(f"Questionnaire {QUESTIONNAIRE_VERSION} · method {METHOD_VERSION}.")
        st.caption("Session memory: Streamlit keeps widget values in server memory per browser session and may "
                   "discard a disconnected session after `server.disconnectedSessionTTL` (default 120 seconds). "
                   "Usage statistics are off in `.streamlit/config.toml`.")


# --------------------------------------------------------------------------- page

groups = group_by_course(result.entries)
if not groups:
    st.error("No instructor responses could be loaded. Add ?admin=1 to the page address and check "
             "'Technical details' in the sidebar.")
    st.stop()

if st.session_state.get("course") not in groups:
    st.session_state.pop("course", None)
# Read up front: the demo strip above the panes depends on the answers, and is drawn before the widgets.
group = groups[st.session_state.get("course", next(iter(groups)))]
entry_for = {e.profile.section_id: e for e in group}

values = {d: st.session_state[f"pref_{d}"] or None for d in DIMENSIONS}
answered = sum(v is not None for v in values.values())
weights = {d: 0 if values[d] is None else st.session_state[f"imp_{d}"] for d in DIMENSIONS}
prefs = StudentPreferences(values, weights)
active_example = next((k for k, s in DEMO_STUDENTS.items() if s == prefs), None) if synthetic else None
comparison = compare_sections(prefs, [e.profile for e in group])

if st.session_state.get("compact"):
    st.html(f'<header class="cf-topbar">{FOX}<h1>{escape(PRODUCT_NAME)}</h1><p>{escape(TAGLINE)}</p></header>')
else:
    head, _, tail = TAGLINE.rpartition(". ")
    with st.container(key="hero"):
        st.html('<header class="cf-hero"><p class="cf-eyebrow">Marist Red Foxes · Course planning</p>'
                f'<div class="cf-wordmark">{FOX}<h1>{escape(PRODUCT_NAME)}</h1></div>'
                f'<p class="cf-tagline">{escape(head)}. <em>{escape(tail)}</em></p>'
                "<p class=\"cf-description\">Compare sections of the same course using instructors' descriptions "
                "of how their classes run, matched to what you prefer for this course.</p></header>")
        if synthetic:
            with st.container(key="hero-examples"):
                for column, key in zip(st.columns(len(DEMO_STUDENTS)), DEMO_STUDENTS):
                    with column:
                        st.button(f"Try example student {key}", on_click=load_example, args=(key,), type="primary",
                                  key=f"main_example_{key}", width="stretch")
                        st.html(f'<p class="cf-cta-note">{escape(DEMO_STUDENT_SUMMARIES[key])}</p>')

if synthetic:
    st.html('<p class="cf-notice cf-data-notice" role="note"><strong>Synthetic demo.</strong> Every instructor and '
            "answer here is fictional, for demonstration only.</p>")
else:
    st.html(f'<p class="cf-notice cf-data-notice" role="note"><strong>Pilot data.</strong> Instructor answers are '
            f"self-reported through the {escape(PRODUCT_NAME)} form and shown with their permission.</p>")

if active_example:
    other = next(k for k in DEMO_STUDENTS if k != active_example)
    with st.container(key="example-strip"):
        note, switch = st.columns([5, 2], vertical_alignment="center")
        note.html(f'<p class="cf-example"><strong>Example student {active_example} (fictional):</strong> '
                  f"{escape(DEMO_STUDENT_SUMMARIES[active_example])}</p>")
        switch.button(f"Switch to student {other}", key="switch_example", on_click=load_example, args=(other,),
                      type="primary", width="stretch")

with st.container(key="workspace"):
    answers_column, results_column = st.columns([5, 7], gap="large")

with answers_column, st.container(key="answers-pane"):
    step(1, "Choose a course")
    course = st.selectbox(
        "Course and term", options=list(groups), format_func=lambda key: group_label(groups[key]), key="course"
    )
    st.html(f'<p class="cf-small">{plural(len(group), "instructor")} answered for this course. Prerequisites, seats '
            "and registration eligibility are not checked.</p>")

    step(2, "What matters to you?")
    st.html('<p class="cf-intro">Answer only what you care about; anything left at &#x27;No preference&#x27; '
            f"isn&#x27;t used. Then say how important each answer is. {escape(PRIVACY_SHORT)}</p>")
    left, right = st.columns([3, 2], vertical_alignment="bottom")
    with left:
        label = f"{answered} of {len(DIMENSIONS)} questions answered"
        st.html(f'<p class="cf-progress-label">{label}</p><progress class="cf-bar" value="{answered}" '
                f'max="{len(DIMENSIONS)}" aria-label="{label}"></progress>')
    with right:
        st.button("Clear my answers", on_click=reset_answers, disabled=answered == 0, width="stretch")
    for heading, keys in QUESTION_GROUPS:
        st.html(f'<h3 class="cf-group">{escape(heading)}</h3>')
        for key in keys:
            render_question(QUESTION_BY_KEY[key])

# On a phone the panes stack; a demo jumps straight to its results instead of six questions down the page.
with results_column, st.container(key="results-pane-first" if active_example else "results-pane"):
    step(3, "Your comparison")
    if comparison.mode == MODE_NO_PREFERENCES:
        st.html('<div class="cf-empty"><strong>Your matches appear here, live.</strong><p class="cf-notice" '
                'style="background:none;padding:0">Answer at least one question to see alignment scores. Until then, '
                "you can compare all the instructors&#x27; answers below.</p></div>")
        with st.container(key="page-sections"):
            render_side_by_side(group)
            render_method()
    else:
        if comparison.mode == MODE_RANKED:
            names, score, tied = closest(comparison, entry_for)
            st.html(f'<section class="cf-banner"><div class="cf-banner-top">{ring_html(score, "cf-ring-hero", label=False)}'
                    f'<p class="cf-summary">Closest {"matches" if tied else "match"} to your answers: <strong>'
                    f'{escape(names)}, {"tied at" if tied else "at"} {score}/100.</strong></p></div>'
                    f"{leaderboard_html(comparison, entry_for)}</section>")
            st.html('<p class="cf-small">Instructors are ordered by how closely their answers agree with yours. Equal '
                    "scores share a rank, and small differences can come from a single answer, so read the reasons "
                    "too.</p>")
        elif comparison.mode == MODE_SINGLE_OPTION:
            only = comparison.ranked[0].result
            st.html(f'<p class="cf-notice">Only <strong>{escape(entry_for[only.section_id].name)}</strong> answered '
                    "every question you rated, so there is no one to rank them against.</p>")
        elif comparison.mode == MODE_UNRANKED_INCOMPLETE:
            st.html('<p class="cf-notice">No instructor answered every question you rated, so nothing is ranked. See '
                    "what&#x27;s missing below, or set a question to &#x27;No preference&#x27;.</p>")
        st.html('<ul class="cf-legend" aria-label="What the chart shows">'
                '<li><span class="cf-dot-you" aria-hidden="true"></span>Your answer</li>'
                '<li><span class="cf-dot-them" aria-hidden="true"></span>Instructor&#x27;s answer</li>'
                '<li><span class="cf-pips" aria-hidden="true" style="margin:0"><i class="on"></i><i class="on"></i><i></i>'
                "</span>How much it matters to you</li></ul>")
        for ranked in comparison.ranked:
            rank = ranked.rank if comparison.mode == MODE_RANKED else None
            render_card(ranked.result, entry_for[ranked.result.section_id], rank)
        if comparison.needs_more_info:
            st.html('<h3 class="cf-more">More information needed</h3><p class="cf-small">These instructors didn&#x27;t '
                    "give one answer to a question you rated, so they can&#x27;t be compared fairly with instructors "
                    "who answered everything.</p>")
            for r in comparison.needs_more_info:
                render_card(r, entry_for[r.section_id], None)
        with st.container(key="page-sections"):
            render_side_by_side(group)
            render_method()

with demo_slot:
    st.html(f'<p class="cf-side-eyebrow">{FOX}{escape(PRODUCT_NAME)}{" / Demo" if synthetic else ""}</p>'
            '<span class="cf-side-rule" aria-hidden="true"></span>')
    if synthetic:
        st.html('<h2 class="cf-side-h">Two-student demo</h2><p class="cf-side-p">Fictional students, same course: '
                "different preferences lead to different matches.</p>")
        for key in DEMO_STUDENTS:
            st.button(f"Example student {key}", on_click=load_example, args=(key,), width="stretch",
                      type="primary" if active_example == key else "secondary")
            st.html(f'<p class="cf-side-p">{escape(DEMO_STUDENT_SUMMARIES[key])}</p>'
                    f'<p class="cf-side-result">{escape(demo_outcome(key, group, entry_for))}</p>')

st.html(f'<footer class="cf-footer"><p><strong>About your answers.</strong> {escape(PRIVACY_FULL)}</p>'
        f"<p>{escape(PRODUCT_NAME)} is the working name of an unofficial student project, "
        "not affiliated with or endorsed by Marist University.</p></footer>")
