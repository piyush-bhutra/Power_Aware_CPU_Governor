"""Streamlit controls exercise the same player for synthetic and saved sessions."""
import importlib
from pathlib import Path

from streamlit.testing.v1 import AppTest


def app():
    return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'daybreak/app.py'), default_timeout=20).run()


def test_autoplay_pause_resume_restart_speed_and_manual_navigation():
    at = app()
    assert not at.exception
    assert at.session_state['player'].playing
    at.button(key='pause').click().run()
    assert not at.session_state['player'].playing
    at.slider(key='tick_control').set_value(23).run()
    at.button(key='previous').click().run()
    assert at.session_state['player'].tick == 22
    at.selectbox(key='speed').set_value(4.0).run()
    assert at.session_state['player'].speed == 4.0
    at.button(key='play').click().run()
    assert at.session_state['player'].playing
    at.button(key='restart').click().run()
    assert at.session_state['player'].tick == 1
    assert not at.exception


def test_windows_collect_disabled_and_never_spawned(monkeypatch):
    collection = importlib.import_module('daybreak.collection')
    monkeypatch.setattr(collection.sys, 'platform', 'win32')
    monkeypatch.setattr(collection.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(AssertionError('spawn')))
    at = app()
    assert at.button(key='collect').disabled
    assert not at.exception


def test_redundant_slider_sync_does_not_pause_autoplay():
    at = app()
    assert at.slider(key='tick_control').disabled
    at.run()
    assert at.session_state['player'].playing


def test_browser_slider_echo_cannot_interrupt_running_clock():
    # Inject the delayed callback directly; current browser disables the slider.
    at = AppTest.from_string('''
import streamlit as st
from daybreak.player import Player
from daybreak.playback_ui import seek
p = Player('synthetic', 34, tick=11)
p.play(100)
st.session_state['player'] = p
st.session_state['tick_control'] = 10
seek()
''').run()
    assert not at.exception
    assert at.session_state['player'].playing
    assert at.session_state['player'].tick == 11


def test_first_collection_start_error_is_visible(monkeypatch):
    import daybreak.playback_ui as ui
    def failed(*args, **kwargs):
        raise OSError('fixture child launch failed')
    monkeypatch.setattr(ui.Collection, 'start', failed)
    from types import SimpleNamespace
    monkeypatch.setattr(ui, 'sys', SimpleNamespace(platform='linux'))
    at = app()
    at.button(key='collect').click().run()
    assert any('fixture child launch failed' in item.value for item in at.error)
