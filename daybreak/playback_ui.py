"""Session selection and common controls, rendered inside one timed fragment."""
import sys
import time

import streamlit as st

from daybreak.collection import Collection
from daybreak.player import Player
from daybreak.sessions import list_sessions, load_session
from presentation.adapter import load_replay

SYNTHETIC = 'Verified synthetic scenario'


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
        job = Collection.start(current=st.session_state.get('collection'))
        st.session_state['collection'] = job
        st.session_state.pop('collection_consumed', None)
        st.session_state.pop('collection_error', None)
        ensure_player().pause()
    except (OSError, RuntimeError) as error:
        st.session_state['collection_error'] = str(error)


def cancel():
    job = st.session_state.get('collection')
    if job is not None:
        job.cancel()


def poll_collection(apply=True):
    job = st.session_state.get('collection')
    if job is None:
        if st.session_state.get('collection_error'):
            st.error(st.session_state['collection_error'])
        return
    result = job.poll()
    if result['status'] == 'collecting':
        count = max(0, min(5, result.get('count', 0)))
        st.progress(count / 5, text=f'Collecting actual Linux intervals: {count} / 5 · cancel available · no retries')
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
            st.session_state['collection_error'] = result.get('error', result['status'])
    if st.session_state.get('collection_error'):
        st.error(st.session_state['collection_error'])


def controls():
    p = ensure_player()
    poll_collection()
    saved = {str(path.resolve()): path for path in list_sessions()}
    options = [SYNTHETIC, *saved]
    st.session_state.setdefault('source_choice', p.source)
    st.session_state.setdefault('speed', p.speed)
    # Retain a validated loaded source even if a folder is temporarily unavailable.
    if p.source not in options:
        options.append(p.source)
    source, action, stop = st.columns([3, 1, 1], vertical_alignment='bottom')
    source.selectbox('Session source', options, key='source_choice', disabled=active_collection(),
                     format_func=lambda key: key if key == SYNTHETIC else 'Saved Linux · ' + key.replace('\\', '/').split('/')[-1])
    choice = st.session_state['source_choice']
    if choice != p.source:
        data = load_replay() if choice == SYNTHETIC else load_session(choice)
        st.session_state['dataset'] = data
        p.switch(choice, len(data.frames), time.monotonic())
    action.button('Collect Live Data', key='collect', on_click=collect,
                  disabled=sys.platform != 'linux' or active_collection())
    stop.button('Cancel collection', key='cancel_collection', on_click=cancel, disabled=not active_collection())
    if sys.platform != 'linux':
        st.caption('Fresh collection requires Linux /proc/stat. Synthetic and saved Linux replay work on Windows.')
    else:
        st.caption('Explicit action only: five background intervals; no generated load, sudo or hardware actuation. Saved sessions are historical.')
    st.session_state['tick'] = p.tick
    if not p.playing:
        st.session_state['tick_control'] = p.tick
    else:
        st.session_state.setdefault('tick_control', p.tick)
    play, pause, again, previous, next_button, speed = st.columns([1, 1, 1, .6, .6, 1.5], vertical_alignment='bottom')
    play.button('Resume' if p.tick > 1 else 'Play', key='play', on_click=toggle_play, args=(True,), disabled=p.playing or p.complete or active_collection())
    pause.button('Pause', key='pause', on_click=toggle_play, args=(False,), disabled=not p.playing)
    again.button('Restart', key='restart', on_click=restart, disabled=active_collection())
    previous.button('←', key='previous', help='Previous tick; pauses playback', on_click=seek, args=(-1,), disabled=p.tick == 1)
    next_button.button('→', key='next', help='Next tick; pauses playback', on_click=seek, args=(1,), disabled=p.complete)
    speed.selectbox('Playback speed', [.5, 1.0, 2.0, 4.0], key='speed', format_func=lambda value: f'{value:g}×', on_change=speed_changed)
    st.slider('Selected replay tick', 1, p.total, key='tick_control', on_change=seek, disabled=p.playing, help='Pause to seek to an exact tick')
    st.button('Reset', key='reset', on_click=seek, kwargs={'reset': True}, help='Return to tick 1 and pause')
    return st.session_state['dataset']
