"""Session selection and common controls, rendered inside one timed fragment."""
import sys
import time
import json

import streamlit as st

from daybreak.collection import Collection
from daybreak.player import Player
from daybreak.sessions import list_sessions, load_session
from presentation.adapter import load_replay
from daybreak.ui_text import session_label

SYNTHETIC = 'Verified synthetic scenario'
SAMPLE_CHOICES = (5, 10, 20)


def ensure_player():
    if 'player' not in st.session_state:
        data = load_replay()
        st.session_state['dataset'] = data
        st.session_state['player'] = Player(SYNTHETIC, len(data.frames))
        st.session_state['player'].play(time.monotonic())
        st.session_state['source_choice'] = SYNTHETIC
    return st.session_state['player']


def active_collection():
    job = st.session_state.get('collection')
    return job is not None and job.active


def toggle_play(playing):
    p = ensure_player()
    p.play(time.monotonic()) if playing else p.pause()


def restart():
    ensure_player().restart(time.monotonic())


def seek(delta=None, reset=False):
    p = ensure_player()
    # Disabled during playback: ignore delayed browser echoes of older slider values.
    if delta is None and not reset and p.playing:
        return
    p.seek(1 if reset else (p.tick + delta if delta is not None else st.session_state['tick_control']))


def speed_changed():
    ensure_player().set_speed(st.session_state['speed'], time.monotonic())


def collect():
    try:
        job = Collection.start(current=st.session_state.get('collection'),
                               count=st.session_state.get('collect_count', SAMPLE_CHOICES[0]))
        st.session_state['collection'] = job
        st.session_state.pop('collection_consumed', None)
        st.session_state.pop('collection_error', None)
        ensure_player().pause()
    except (OSError, RuntimeError, ValueError) as error:
        st.session_state['collection_error'] = str(error)


def cancel():
    job = st.session_state.get('collection')
    if job is not None:
        job.cancel()


def poll_collection(apply=True, render=True):
    job = st.session_state.get('collection')
    if job is None:
        if render and st.session_state.get('collection_error'):
            st.error(st.session_state['collection_error'])
        return
    result = job.poll()
    if result['status'] == 'collecting':
        total = getattr(job, 'count', SAMPLE_CHOICES[0])
        count = max(0, min(total, result.get('count', 0)))
        if render:
            st.progress(count / total, text=f'Collecting actual Linux intervals: {count} / {total} · cancel available · no retries')
    elif st.session_state.get('collection_consumed') != str(job.folder):
        if not apply:
            return True  # apply new source before its widget is instantiated on full rerun
        st.session_state['collection_consumed'] = str(job.folder)
        if result['status'] == 'validated':
            try:
                folder = (job.folder / result['folder']).resolve()
                if folder.parent != job.folder.resolve():
                    raise ValueError('Invalid child result path')
                data = load_session(folder)
                st.session_state['dataset'] = data
                st.session_state['source_choice'] = str(folder)
                ensure_player().switch(str(folder), len(data.frames), time.monotonic())
            except (OSError, ValueError, KeyError, TypeError) as error:
                st.session_state['collection_error'] = f'Collected session rejected: {error}'
        else:
            st.session_state['collection_error'] = failure_message(result)
    if render and st.session_state.get('collection_error'):
        st.error(st.session_state['collection_error'])


def failure_message(result):
    """Plain words for the attempt cap; other failures keep their recorded error."""
    if result.get('reason') == 'attempt_cap':
        return ('Collection stopped: VM timing was unstable, so too many intervals had to be discarded '
                'before enough valid samples were collected. Close other applications and retry. '
                f'Evidence retained at {result.get("evidence")}.')
    return result.get('error', result['status'])


def controls():
    p = ensure_player()
    if not active_collection():
        poll_collection(render=False)
    saved = {str(path.resolve()): path for path in list_sessions()}
    options = [SYNTHETIC, *saved]
    st.session_state.setdefault('source_choice', p.source)
    st.session_state.setdefault('speed', p.speed)
    # Retain a validated loaded source even if a folder is temporarily unavailable.
    if p.source not in options:
        options.append(p.source)
    labels = {SYNTHETIC: SYNTHETIC}
    for index, (key, path) in enumerate(saved.items(), 1):
        try:
            metadata = json.loads((path / 'metadata.json').read_text(encoding='utf-8'))
            labels[key] = f'{session_label(metadata)} · #{index}'
        except (OSError, ValueError, TypeError, AttributeError):
            labels[key] = f'Unreadable session · #{index}'
    st.selectbox('Session source', options, key='source_choice', disabled=active_collection(),
                 format_func=lambda key: labels.get(key, 'Previously loaded session'))
    choice = st.session_state['source_choice']
    if choice != p.source:
        with st.spinner('Validating session and preparing replay…'):
            data = load_replay() if choice == SYNTHETIC else load_session(choice)
        st.session_state['dataset'] = data
        p.switch(choice, len(data.frames), time.monotonic())
    if not saved:
        st.caption('No saved sessions yet. Explore the synthetic example, or collect on Linux.')
    st.selectbox('Samples', SAMPLE_CHOICES, key='collect_count', disabled=active_collection(),
                      help='One-second background intervals for Collect Live Data')
    st.button('Collect Live Data', key='collect', on_click=collect, width='stretch',
                  disabled=sys.platform != 'linux' or active_collection())
    if sys.platform != 'linux':
        st.caption('Fresh collection requires Linux /proc/stat. Synthetic and saved Linux replay work on Windows.')
    else:
        st.caption('Explicit action only: 5, 10 or 20 one-second background intervals; no generated load, sudo or hardware actuation. Saved sessions are historical.')
    st.session_state['tick'] = p.tick
    if not p.playing:
        st.session_state['tick_control'] = p.tick
    else:
        st.session_state.setdefault('tick_control', p.tick)
    st.divider()
    play, pause, again = st.columns(3)
    play.button('Resume' if p.tick > 1 else 'Play', key='play', on_click=toggle_play, args=(True,), disabled=p.playing or p.complete or active_collection())
    pause.button('Pause', key='pause', on_click=toggle_play, args=(False,), disabled=not p.playing)
    again.button('Restart', key='restart', on_click=restart, disabled=active_collection())
    previous, next_button = st.columns(2)
    previous.button('Previous', key='previous', help='Previous sample; pauses playback', on_click=seek, args=(-1,), disabled=p.tick == 1 or active_collection())
    next_button.button('Next', key='next', help='Next sample; pauses playback', on_click=seek, args=(1,), disabled=p.complete or active_collection())
    st.selectbox('Playback speed', [.5, 1.0, 2.0, 4.0], key='speed', format_func=lambda value: f'{value:g}×', on_change=speed_changed, disabled=active_collection())
    st.slider('Selected replay sample', 1, p.total, key='tick_control', on_change=seek, disabled=p.playing or active_collection(), help='Pause to seek to an exact sample')
    st.button('Reset', key='reset', on_click=seek, kwargs={'reset': True}, help='Return to sample 1 and pause', disabled=active_collection())
    return st.session_state['dataset']
