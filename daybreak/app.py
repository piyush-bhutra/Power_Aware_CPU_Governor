"""Daybreak Streamlit presentation. Page loads are offline, bounded and read-only."""
from html import escape
import inspect
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from classifier.rules import THRESHOLDS, classify
from daybreak.charts import comparison_figure, energy_figure, evidence_figure, replay_figure
from daybreak.data import comparison_table, inspect_decision, load_comparison, move_tick, observation_table, replay_table
from presentation.adapter import load_observations, load_replay

VIEWS = ('The Replay', 'The Evidence', 'The Comparison', 'Lab Notes')
CHART_CONFIG = {'displaylogo': False, 'scrollZoom': False, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']}


def html(content):
    st.markdown(content, unsafe_allow_html=True)


def ghz(value):
    return f'{value / 1e6:.3f} GHz' if value is not None else 'Unavailable'


def navigate(view):
    st.session_state['view'] = view


def change_tick(delta=0, reset=False):
    tick = 1 if reset else move_tick(st.session_state.get('tick', 1), delta, 34)
    st.session_state['tick'] = tick
    st.session_state['tick_control'] = tick


def select_tick():
    st.session_state['tick'] = st.session_state['tick_control']


def first_transition():
    # Read the verified event instead of copying a transition boundary into UI logic.
    replay = load_replay()
    tick = next(f.tick for f in replay.frames if f.transition)
    st.session_state['tick'] = tick
    st.session_state['tick_control'] = tick


def state_copy(info):
    if info['state'] == 'WAITING':
        return f"Holding {ghz(info['applied_khz'])}. Needs {info['remaining']} more matching sample(s)."
    if info['state'] == 'APPLIED':
        return 'Persistence met. The simulated change is accepted.'
    if info['state'] == 'STABLE':
        return 'Stable class. The simulated level is held.'
    return 'Decision persistence is unavailable.'


def state_card(info):
    streak, k = info['streak'], info['k']
    percent = min(streak, k) / k * 100 if streak is not None else 0
    count = f'{min(streak, k)} / {k}' if streak is not None else 'N/A'
    html(f'''<section class="state-card" aria-label="Inside the governor">
      <div class="state-top"><span>INSIDE THE GOVERNOR</span><span class="badge">T{info['tick']:02d}</span></div>
      <div class="state-core"><div class="ring" style="background:conic-gradient(#d9aa68 {percent}%,#f4eee6 0)">
       <div class="ring-inner">{count}<small>persistent ticks*</small></div></div><div>
       <div class="state-pred">{escape(info['predicted_class'].replace('_', ' '))}</div>
       <div class="state-blurb">{escape(state_copy(info))}</div></div></div>
      <div class="state-bottom"><span>Candidate*<b>{ghz(info['candidate_khz'])}</b></span>
       <span>Applied · simulated<b>{ghz(info['applied_khz'])}</b></span><span>K = {k}</span></div></section>''')


def provenance(data):
    st.caption('Verified source · ' + data.metadata['source_commit'])
    with st.expander('Provenance & original sample identity'):
        st.write(data.metadata['validation'])
        st.code(data.metadata['csv_path'], language=None)
        st.json({key: data.metadata[key] for key in ('source_commit', 'seed', 'k', 'experiment_id', 'workload_label', 'derived_fields')
                 if key in data.metadata})
        st.write(data.metadata['limitations'])


def replay_view():
    replay = load_replay()
    st.session_state.setdefault('tick', 1)
    st.session_state.setdefault('tick_control', st.session_state['tick'])
    tick = st.session_state['tick']
    frame = replay.frames[tick - 1]
    info = inspect_decision(replay, tick)
    left, right = st.columns([1.35, 1], gap='large')
    with left:
        html('<div class="overline">OS LAB / POWER-AWARE CPU GOVERNOR</div>'
             '<div class="hero-title">A little patience.<br>A <em>smarter</em> decision.</div>'
             '<p class="hero-copy">A workload-adaptive policy that waits before it switches. '
             'Follow the signals, inspect the logic, and see hysteresis in action.</p>')
        a, b = st.columns([1.05, 1])
        a.button('Explore the first transition →', type='primary', on_click=first_transition, key='first_transition')
        b.caption('34 verified synthetic ticks\n\nOffline · simulated actuation')
    with right:
        state_card(info)
    with st.container(key='card_pipeline'):
        html('<div class="pipeline"><span><span class="index">01</span>Observe</span>→'
             '<span><span class="index">02</span>Classify</span>→<span><span class="index">03</span>Select</span>→'
             '<strong><span class="index">04</span>Wait</strong>→<span><span class="index">05</span>Apply</span>'
             '<span class="badge">SYNTHETIC REPLAY</span></div>')
    main, inspector = st.columns([2.15, 1], gap='medium')
    with main, st.container(key='card_timeline'):
        st.subheader('The decision timeline')
        st.caption('Violet: utilization & derived candidate · Blue: applied simulated frequency')
        st.plotly_chart(replay_figure(replay, tick), width='stretch', theme=None, config=CHART_CONFIG, key='replay_chart')
        previous, slider, next_button, reset = st.columns([.65, 4, .65, .8], vertical_alignment='bottom')
        previous.button('←', key='previous', help='Previous tick', disabled=tick == 1, on_click=change_tick, args=(-1,))
        with slider:
            st.slider('Selected replay tick', 1, len(replay.frames), key='tick_control', on_change=select_tick)
        next_button.button('→', key='next', help='Next tick', disabled=tick == len(replay.frames), on_click=change_tick, args=(1,))
        reset.button('Reset', key='reset', on_click=change_tick, kwargs={'reset': True})
        st.caption(f'Tick {tick} / {len(replay.frames)} · nominal synthetic time {frame.timestamp:.0f}s · {info["transitions"]} verified transitions so far')
    with inspector, st.container(key='card_inspector'):
        html('<div class="overline">READ THE SIGNALS</div>')
        st.subheader('Why this decision?')
        html(f'<div class="rule">The existing rule classifier predicts <b>{escape(frame.predicted_class.replace("_", " "))}</b>. '
             'The candidate comes from the backend policy, not a separate UI heuristic.</div>')
        for label, value in (
            ('CPU utilization', f'{frame.util_pct:.2f}%'), ('I/O wait', f'{frame.features["iowait_pct"]:.2f}%'),
            ('Context switches', f'{frame.features["ctxt_per_s"]:,.0f} /s'),
            ('Runnable / blocked', f'{frame.features["procs_running"]} / {frame.features["procs_blocked"]}'),
            ('Persistence*', f'{frame.streak} consecutive' if frame.streak is not None else 'Unavailable'),
            ('Transitions so far', str(info['transitions']))):
            html(f'<div class="keyval"><span>{label}</span><b>{escape(value)}</b></div>')
        html(f'<div class="decision">{escape(state_copy(info))}</div>'
             '<span class="badge">Prediction ≠ verified workload label</span>')
        st.caption('*Candidate, persistence and reasons are reconstructed with the existing Policy. Applied outputs match the archive.')
    a, b = st.columns(2)
    with a, st.container(key='card_evidence'):
        html('<div class="overline">THE EVIDENCE MATTERS</div>')
        st.subheader('Real signals. Clear boundaries.')
        st.write('Five archived Linux observations establish background monitoring readiness. This replay uses invented inputs and simulated frequency decisions.')
        st.button('Open evidence register ↗', on_click=navigate, args=('The Evidence',), key='open_evidence')
    with b, st.container(key='card_transition_summary'):
        st.subheader('A deliberate pause, then a change.')
        events = [f.transition for f in replay.frames[:tick] if f.transition]
        if events:
            for event in events:
                st.write(f'T{event.tick:02d} · {ghz(event.previous_khz)} → {ghz(event.new_khz)} · {event.predicted_class}')
        else:
            st.write('No applied transitions yet. Initialization is excluded.')
        st.caption('All three full-run events are verified against the recorded applied frequencies.')
        st.button('Compare all five policies ↗', on_click=navigate, args=('The Comparison',), key='open_comparison')
    provenance(replay)
    with st.expander('Inspect all 34 archived samples'):
        st.dataframe(replay_table(replay), hide_index=True, width='stretch')
        st.caption(info['sample_id'])


def evidence_view():
    observations = load_observations()
    html('<div class="overline">THE EVIDENCE / RECORDED LINUX OBSERVATIONS</div>')
    st.title('Real signals. Clear boundaries.')
    st.write('Five historical guest-kernel observations, captured without generated workloads. These are not live data and are not idle ground truth.')
    table = observation_table(observations)
    a, b, c = st.columns(3)
    a.metric('Archived observations', len(table))
    b.metric('Mean measured CPU utilization', f'{table["CPU %"].mean():.4f}%')
    c.metric('Mean elapsed interval', f'{table["Elapsed seconds"].mean():.4f} s')
    with st.container(key='card_evidence'):
        st.subheader('What the archive establishes')
        st.write('Successful bounded background monitoring, raw-counter consistency and a recorded readiness/cleanup path. No frequency measurements are available.')
        st.caption('It does not establish loaded VM stability, classifier accuracy, physical actuation, measured energy savings or preserved completion time.')
    with st.container(key='card_recorded_chart'):
        st.plotly_chart(evidence_figure(observations), width='stretch', theme=None, config=CHART_CONFIG)
        st.dataframe(table, hide_index=True, width='stretch')
    provenance(observations)


def comparison_view():
    comparison = load_comparison()
    html('<div class="overline">THE COMPARISON / SAME SYNTHETIC INPUTS</div>')
    st.title('Five policies. One fixed trace.')
    st.write('Python policy approximations over the same 34 invented observations. Frequency is simulated; energy and power are uncalibrated model estimates, not physical measurements.')
    a, b = st.columns([1, 1.3])
    with a, st.container(key='card_energy'):
        st.subheader('Modelled energy, not measured savings')
        st.plotly_chart(energy_figure(comparison), width='stretch', theme=None, config=CHART_CONFIG)
    with b, st.container(key='card_comparison_chart'):
        st.subheader('Simulated frequency behavior')
        names = st.multiselect('Policies shown', list(comparison.policies), default=list(comparison.policies), key='policies')
        if names:
            st.plotly_chart(comparison_figure(comparison, names), width='stretch', theme=None, config=CHART_CONFIG)
        else:
            st.info('Select at least one policy to display its archived trace.')
    st.dataframe(comparison_table(comparison), hide_index=True, width='stretch')
    with st.container(key='card_evidence'):
        st.write('Lower modelled energy is not proof of a better performance–energy trade-off. Fixed-input replay does not model how frequency changes workload duration. Completion time, accuracy, throughput and electrical power were not measured here.')
    st.caption(comparison.metadata['summary_validation'])
    provenance(load_replay())


def notes_view():
    html('<div class="overline">LAB NOTES / METHODOLOGY & LIMITATIONS</div>')
    st.title('An explainable systems experiment.')
    a, b = st.columns(2)
    with a, st.container(key='card_notes'):
        st.subheader('From kernel counters to a decision')
        st.markdown('''1. **Observe:** Linux `/proc/stat` reports cumulative CPU times and context switches, plus instantaneous runnable/blocked counts.
2. **Extract:** the existing monitor differences counters and uses measured monotonic intervals. Guest duplication, resets and decreasing iowait are handled explicitly.
3. **Classify:** four transparent, provisional rule classes: CPU-bound, I/O-bound, idle and mixed.
4. **Wait:** the backend Policy requires K=3 consecutive matching predictions. A changed prediction resets its streak.
5. **Apply:** explicit `SimulatedSetter` updates software state. It does not change the physical processor clock.''')
        st.caption('The OS scheduler, process priorities and queue membership are not modified.')
    with b, st.container(key='card_evidence'):
        st.subheader('Three kinds of evidence')
        st.markdown('''**Synthetic replay:** invented counters, real classifier/policy code, simulated frequency.

**Recorded Linux observations:** historical measured guest counters, no measured frequency, no simulated decisions added to that capture.

**Modelled power/energy:** assumed cubic model with constants 21.6 W and 32.4 W. TDP-based assumptions are uncalibrated; no electrical measurements or performance-preservation claim.''')
    with st.expander('The actual classifier and its provisional thresholds', expanded=True):
        st.dataframe([{'Threshold': key, 'Current value (provisional)': value} for key, value in THRESHOLDS.items()], hide_index=True, width='stretch')
        st.code(inspect.getsource(classify), language='python')
    with st.container(key='card_live_limit'):
        st.subheader('VirtualBox & live monitoring')
        st.write('The recorded Ubuntu guest exposes no CPUFreq interface. Loaded stress runs have a history of freezes and timing irregularities. Nothing in this dashboard starts live observation, a collector, artificial load, a subprocess or hardware actuation.')
        st.write('The existing terminal live API uses Linux SIGALRM/setitimer deadlines and writes capture artifacts. Streamlit request threads cannot safely own that process-level signal lifecycle, so web live capture is deferred; offline views are independent of it.')
        st.code('.venv/bin/python -m governorlab --visual\n.venv/bin/python -m governorlab --live --visual', language='bash')
        st.caption('Terminal live mode is Linux-only, user-initiated and separately bounded. These commands are documentation, not actions launched by the web page.')
    st.subheader('Reproducibility')
    st.write('Archive manifests are checked before loading. Replay configuration is seed 11, K=3 and the archived frequency ladder; applied outputs are reconstructed with the existing backend. All five comparison traces and summaries are checked against that same backend. Text-only CRLF checkout differences are distinguished from original CSV/PNG bytes.')
    st.caption('Source commits, sample identity and scientific limitations are available within each evidence surface. No dashboard values are copied from the design preview.')


def main():
    st.set_page_config(page_title='Governorlab · Daybreak', page_icon='◷', layout='wide', initial_sidebar_state='collapsed')
    html('<style>' + (Path(__file__).with_name('theme.css')).read_text(encoding='utf-8') + '</style>')
    brand, navigation = st.columns([1.1, 2.2], vertical_alignment='center')
    with brand:
        html('<div class="brand">Governor<span>lab.</span><small>DAYBREAK</small></div>')
    with navigation:
        st.radio('Dashboard section', VIEWS, horizontal=True, key='view', label_visibility='collapsed')
    view = st.session_state['view']
    try:
        {'The Replay': replay_view, 'The Evidence': evidence_view,
         'The Comparison': comparison_view, 'Lab Notes': notes_view}[view]()
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.error(f'This view could not validate its source data: {error}')
        st.info('No substitute measurements are generated. Restore the original archive and try again; other views remain independently available.')
    html('<div class="footer"><span>Verified sources · synthetic ≠ measured · simulated ≠ physical</span>'
         '<span>Userspace prototype / Linux · VirtualBox</span></div>')


if __name__ == '__main__':
    main()
