"""Website tests using Streamlit's built-in AppTest: runs app.py headlessly, no browser needed.

These cover first load, the two-student demo, answering questions, ties,
incomplete answers, the single-option course, reset, page language, the
privacy promise and the logo.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")


@pytest.fixture
def app():
    return AppTest.from_file(APP, default_timeout=30).run()


def visible_text(fragment):
    """HTML -> the text a reader sees (no CSS, no embedded image data, no tags)."""
    fragment = re.sub(r"<style.*?</style>", " ", fragment, flags=re.S)
    fragment = re.sub(r'src="data:[^"]*"', "", fragment)
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def html_of(block):
    return " ".join(h.value for h in block.html)


def page(block):
    """Everything the page shows: custom HTML plus Streamlit text elements."""
    parts = [visible_text(html_of(block))]
    parts += [e.value.replace("\\", "") for kind in ("markdown", "caption", "error") for e in getattr(block, kind)]
    parts += [b.label for b in block.button]
    return " ".join(parts)


def scores(at):
    return re.findall(r'aria-label="Alignment (\d+)/100"', html_of(at))


def summary(at):
    return " ".join(visible_text(h.value) for h in at.html if 'class="cf-summary"' in h.value)


def set_answer(at, dimension, value, importance=None):
    at.pills(key=f"pref_{dimension}").set_value(value).run()
    if importance is not None:
        at.pills(key=f"imp_{dimension}").set_value(importance).run()


def test_first_load_shows_synthetic_notice_and_no_scores(app):
    assert not app.exception
    assert "Synthetic demo. Every instructor and answer here is fictional" in page(app)
    assert "Answer at least one question to see alignment scores" in page(app)
    assert scores(app) == []
    assert len(app.dataframe) == 1  # the side-by-side table is shown instead


def test_masthead_and_sidebar_show_the_fox_mark(app):
    hero = next(h.value for h in app.html if 'class="cf-hero"' in h.value)
    assert '<img class="cf-fox" alt="" src="data:image/svg+xml;base64,' in hero
    assert "cf-fox" in html_of(app.sidebar)
    assert (ROOT / "assets" / "classfit-fox.png").exists()


def test_stylesheet_survives_the_html_sanitizer(app):
    # st.html's sanitizer deletes a whole <style> block whose text looks like it contains a tag.
    css = next(h.value for h in app.html if "<style>" in h.value)
    assert not re.search(r"<[/\w!]", css.replace("<style>", "").replace("</style>", ""))


def test_demo_click_collapses_the_hero_so_results_fill_the_screen(app):
    assert any('class="cf-hero"' in h.value for h in app.html)
    app.button(key="main_example_1").click().run()
    assert not any('class="cf-hero"' in h.value for h in app.html)
    assert any('class="cf-topbar"' in h.value for h in app.html)
    next(b for b in app.button if b.label == "Clear my answers").click().run()
    assert any('class="cf-hero"' in h.value for h in app.html)


def test_typing_an_answer_leaves_the_hero_in_place(app):
    set_answer(app, "discussion", 4)  # collapsing here would move the page under the cursor
    assert any('class="cf-hero"' in h.value for h in app.html)


def test_leaderboard_lists_unranked_instructors_without_a_score(app):
    app.sidebar.button[1].click().run()
    board = next(h.value for h in app.html if 'class="cf-board"' in h.value)
    assert re.findall(r'cf-board-score">(\d+)<', board) == ["90", "75", "65", "23"]
    assert "Not ranked: missing an answer, never guessed" in visible_text(board)
    assert "53" not in visible_text(board)  # C's partial score stays inside its card's sentence


def test_answer_chart_plots_each_rated_question_and_skips_the_rest(app):
    app.sidebar.button[0].click().run()  # student 1 has no preference on following the plan
    card = next(h.value for h in app.html if "#1 · Instructor B" in h.value)
    assert card.count('class="cf-mark-you"') == 5
    assert "Following the plan" not in card
    assert "You: Almost always. Instructor: Almost always." in card


def test_every_question_shows_five_labelled_answers_and_no_preference(app):
    assert app.pills(key="pref_discussion").options == [
        "Rarely", "Sometimes", "About half", "Often", "Almost always", "No preference"]
    assert app.pills(key="pref_exams").options == ["0–20%", "21–40%", "41–60%", "61–80%", "81–100%", "No preference"]
    assert all(app.pills(key=f"pref_{d}").value == 0 for d in
               ("discussion", "practice", "plan", "balance", "exams", "collaboration"))


def test_example_student_1_matches_the_engine(app):
    app.sidebar.button[0].click().run()
    assert scores(app) == ["91", "86", "70", "64", "45"]
    assert "Closest match to your answers: Instructor B (fictional), at 91/100." in summary(app)
    assert "More information needed" not in page(app)


def test_example_student_2_gets_a_different_closest_match_and_c_is_not_ranked(app):
    app.sidebar.button[1].click().run()
    assert scores(app) == ["90", "75", "65", "23"]  # C's partial score is not shown as a big number
    assert "Closest match to your answers: Instructor A (fictional), at 90/100." in summary(app)
    text = page(app)
    assert "More information needed" in text and "Not ranked" in text
    assert "Not comparable on following the plan" in text
    assert "alignment is 53/100" in text  # the partial score stays inside its sentence


def test_switch_button_moves_between_the_two_demo_students(app):
    app.sidebar.button[0].click().run()
    assert "Example student 1 (fictional)" in page(app)
    app.button(key="switch_example").click().run()
    assert "Example student 2 (fictional)" in page(app)
    assert scores(app)[0] == "90"


def test_demo_panel_shows_each_students_closest_match(app):
    sidebar = page(app.sidebar)
    assert "Closest match in PM 101 · Spring 2027: Instructor B (fictional), at 91/100." in sidebar
    assert "Closest match in PM 101 · Spring 2027: Instructor A (fictional), at 90/100." in sidebar


def test_answering_one_question_produces_a_ranking(app):
    set_answer(app, "discussion", 4, importance=3)
    assert not app.exception
    found = [int(s) for s in scores(app)]
    assert found == sorted(found, reverse=True)
    assert len(found) == 5  # every PM 101 instructor answered the discussion question


def test_importance_starts_in_the_middle(app):
    set_answer(app, "exams", 1)
    assert app.pills(key="imp_exams").value == 2
    assert app.pills(key="imp_exams").options == ["Slightly important", "Important", "Very important"]


def test_tied_instructors_share_the_summary_and_the_rank(app):
    set_answer(app, "exams", 2)  # C and E both answered 21–40%
    assert ("Closest matches to your answers: Instructor C (fictional) and Instructor E (fictional), "
            "tied at 100/100.") in summary(app)
    text = page(app)
    assert "#1 · Instructor C (fictional)" in text and "#1 · Instructor E (fictional)" in text


def test_rating_a_question_an_instructor_left_open_keeps_them_unranked(app):
    set_answer(app, "plan", 5)
    assert len(scores(app)) == 4  # A, B, D, E; C answered "Varies / unable to answer"
    assert "Not comparable on following the plan" in page(app)


def test_single_option_course_says_so_honestly(app):
    app.selectbox(key="course").select_index(1).run()  # PM 102: G left the exams question open
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert "Only Instructor F (fictional) answered every question you rated" in page(app)
    assert scores(app) == ["20"]


def test_reset_clears_answers(app):
    app.sidebar.button[0].click().run()
    assert scores(app)
    next(b for b in app.button if b.label == "Clear my answers").click().run()
    assert scores(app) == []
    assert all(app.pills(key=f"pref_{d}").value == 0 for d in
               ("discussion", "practice", "plan", "balance", "exams", "collaboration"))
    assert next(b for b in app.button if b.label == "Clear my answers").disabled


def test_students_see_no_technical_details(app):
    assert len(app.sidebar.expander) == 0
    text = page(app)
    assert "File fingerprint" not in text and "Row 10 skipped" not in text and "Questionnaire v2" not in text


def test_organizers_see_technical_details_with_admin_in_the_address():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["admin"] = "1"
    at.run()
    (technical,) = at.sidebar.expander
    assert technical.label == "Technical details"
    inside = page(technical)
    assert "File fingerprint" in inside and "Questionnaire v2" in inside and "Row 10 skipped" in inside


def test_privacy_wording_matches_the_implementation(app):
    text = page(app).lower()
    assert "nothing you enter" not in text  # the old, overstated promise
    assert "never written to a file or database" in text
    assert "access logs" in text


def test_using_the_app_writes_no_files(app):
    def snapshot():
        skip = {".git", ".venv", "__pycache__", ".pytest_cache"}
        return {p: p.stat().st_mtime_ns for p in ROOT.rglob("*") if p.is_file() and not skip & set(p.parts)}
    before = snapshot()
    app.sidebar.button[0].click().run()
    set_answer(app, "plan", 5, importance=3)
    next(b for b in app.button if b.label == "Clear my answers").click().run()
    assert snapshot() == before


@pytest.mark.parametrize("word", ["probability", "success", "proven", "best", "worst", "guarantee"])
def test_page_avoids_forbidden_claims(app, word):
    # Section F applies to the whole page, not only the engine's explanations.
    pages = [page(app).lower()]
    for button in (0, 1):
        app.sidebar.button[button].click().run()
        pages.append(page(app).lower())
    assert not any(re.search(rf"\b{word}\b", text) for text in pages)
