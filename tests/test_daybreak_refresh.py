"""UI regression checks; collection uses a fake job and never samples."""
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def app():
    return AppTest.from_file(str(ROOT / 'daybreak/app.py'), default_timeout=20).run()


def test_controls_in_sidebar_and_summary_above_chart():
    at = app()
    assert not at.exception
    assert at.sidebar.selectbox(key='source_choice')
    assert any('What happened' in item.value for item in at.subheader)
    assert any(item.label == 'How to read this' for item in at.expander)


def test_collecting_has_one_progress_panel_and_no_replay(monkeypatch, tmp_path):
    import daybreak.playback_ui as ui
    job = SimpleNamespace(folder=tmp_path, active=True, count=10,
                          poll=lambda: {'status': 'collecting', 'count': 2})
    monkeypatch.setattr(ui.Collection, 'start', lambda **kwargs: job)
    monkeypatch.setattr(ui, 'sys', SimpleNamespace(platform='linux'))
    at = app()
    at.button(key='collect').click().run()
    assert not at.exception
    assert len(at.get('progress')) == 1
    assert len(at.get('plotly_chart')) == 0
    assert not at.button(key='cancel_collection').disabled


def test_summary_describes_verified_transition():
    from daybreak.ui_text import what_happened
    from presentation.adapter import load_replay
    text = what_happened(load_replay())
    assert '34 samples' in text
    assert 'sample 13' in text
    assert '5.100' in text and '4.233' in text
    assert 'simulated' in text.lower()


def test_session_label_has_date_count_and_quality():
    from daybreak.ui_text import session_label
    text = session_label({'started_utc': '2026-10-19T10:15:00Z',
                          'actual_sample_count': 10, 'timing_quality': 'degraded'})
    assert '19 Oct 2026' in text and '10:15' in text
    assert '10 samples' in text and 'Timing degraded' in text


def test_session_label_does_not_invent_missing_metadata():
    from daybreak.ui_text import session_label
    text = session_label({})
    assert 'Date unavailable' in text and 'count unavailable' in text
    assert 'not recorded' in text
