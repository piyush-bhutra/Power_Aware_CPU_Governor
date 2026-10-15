"""Real Streamlit widget reruns; no server, live monitoring or synthetic UI values."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1]


def app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(ROOT / 'daybreak/app.py'), default_timeout=20).run()


def test_replay_navigation_slider_next_previous_and_reset():
    at = app()
    assert not at.exception
    assert at.slider(key='tick_control').value == 1
    at.button(key='next').click().run()
    assert at.slider(key='tick_control').value == 2
    at.slider(key='tick_control').set_value(11).run()
    assert at.session_state['tick'] == 11
    at.button(key='next').click().run()
    assert at.session_state['tick'] == 12
    at.button(key='previous').click().run()
    assert at.session_state['tick'] == 11
    at.button(key='reset').click().run()
    assert at.session_state['tick'] == 1
    assert not at.exception


@pytest.mark.parametrize('view', ['The Evidence', 'The Comparison', 'Lab Notes'])
def test_all_surfaces_render_and_preserve_replay_cursor(view):
    at = app()
    assert not at.exception
    at.slider(key='tick_control').set_value(13).run()
    at.radio(key='view').set_value(view).run()
    assert not at.exception
    assert at.session_state['tick'] == 13
    at.radio(key='view').set_value('The Replay').run()
    assert at.slider(key='tick_control').value == 13


def test_missing_evidence_is_an_error_without_invented_replacement(monkeypatch):
    import presentation.adapter
    def missing():
        raise ValueError('archive missing for test')
    monkeypatch.setattr(presentation.adapter, 'load_observations', missing)
    at = app()
    at.radio(key='view').set_value('The Evidence').run()
    assert not at.exception
    assert any('archive missing for test' in element.value for element in at.error)
    assert len(at.dataframe) == 0
