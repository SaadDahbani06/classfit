"""Website tests using Streamlit's built-in AppTest: runs app.py headlessly, no browser needed.

These cover the end-to-end manual checks from roadmap section X: first load,
a successful comparison, changing preferences, no preferences, incomplete
evidence and reset.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app():
    return AppTest.from_file(APP, default_timeout=30).run()


def metrics(at):
    return [(m.label, m.value) for m in at.metric]


def set_answer(at, dimension, value, importance=None):
    at.selectbox(key=f"pref_{dimension}").set_value(value).run()
    if importance is not None:
        at.selectbox(key=f"imp_{dimension}").set_value(importance).run()


def test_first_load_shows_synthetic_banner_and_no_scores(app):
    assert not app.exception
    assert any("Synthetic demo" in w.value for w in app.warning)
    assert any("Answer at least one question" in i.value for i in app.info)
    assert metrics(app) == []
    assert len(app.dataframe) == 1  # the side-by-side table is shown instead


def test_example_student_1_matches_the_engine(app):
    app.sidebar.button[0].click().run()
    assert metrics(app) == [
        ("Alignment", "89/100"),
        ("Alignment", "78/100"),
        ("Alignment", "61/100"),
        ("Alignment", "28/100"),
        ("Partial (not ranked)", "96/100"),
    ]
    assert any("More information needed" in m.value for m in app.markdown)


def test_switching_to_example_student_2_changes_the_top_match(app):
    app.sidebar.button[0].click().run()
    app.sidebar.button[1].click().run()
    assert metrics(app)[0] == ("Alignment", "100/100")
    assert any("#1 · Instructor B" in m.value.replace("\\", "") for m in app.markdown)


def test_answering_one_question_produces_a_ranking(app):
    set_answer(app, "format", 1, importance=3)
    assert not app.exception
    scores = [int(value.split("/")[0]) for label, value in metrics(app) if label == "Alignment"]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == 5  # format is known for all five PM101 instructors


def test_rating_only_a_dimension_with_gaps_keeps_incomplete_instructors_unranked(app):
    set_answer(app, "assessment", 5)
    labels = [label for label, _ in metrics(app)]
    assert labels.count("Partial (not ranked)") == 0  # C has no assessment data at all...
    assert any("insufficient evidence" in m.value for m in app.markdown)  # ...so it gets no score


def test_reset_clears_answers(app):
    app.sidebar.button[0].click().run()
    assert metrics(app)
    next(b for b in app.button if b.label == "Clear my answers").click().run()
    assert metrics(app) == []
    assert all(app.selectbox(key=f"pref_{d}").value == 0
               for d in ("format", "assessment", "collaboration", "structure"))


def test_second_course_can_be_selected(app):
    app.selectbox(key="course").select_index(1).run()
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert len(metrics(app)) == 2  # PM102 has two consenting instructors


def test_best_fit_banner_names_the_top_instructor(app):
    app.sidebar.button[0].click().run()
    assert any("Your best fit" in s.value and "Instructor A" in s.value.replace("\\", "") and "89/100" in s.value
               for s in app.success)


def test_main_page_example_button_loads_example(app):
    next(b for b in app.button if b.key == "main_example_2").click().run()
    assert metrics(app)[0] == ("Alignment", "100/100")
    assert not [b for b in app.button if b.key == "main_example_2"]  # hidden once answers exist
