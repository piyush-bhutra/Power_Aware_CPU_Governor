"""Offline dashboard data contracts, using real archives and backend outputs."""
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def data_module():
    return importlib.import_module('daybreak.data')


def test_comparison_contains_all_five_verified_archived_policies():
    comparison = data_module().load_comparison()
    assert set(comparison.policies) == {'performance', 'powersave', 'ondemand', 'conservative', 'ours'}
    assert all(len(rows) == 34 for rows in comparison.policies.values())
    assert comparison.summaries['ours']['freq_change_count'] == 3
    assert comparison.policies['ours'][12]['target_khz'] == 4233333
    assert comparison.policies['ondemand'][12]['target_khz'] == 5100000
    assert comparison.metadata['frequency_control'] == 'simulated'


def test_comparison_rejects_summary_drift(monkeypatch):
    from benchmark import summarize
    original = summarize.summarize
    def wrong(rows, interval_s=1):
        result = original(rows, interval_s)
        return {**result, 'total_energy_j': result['total_energy_j'] + 1}
    monkeypatch.setattr(summarize, 'summarize', wrong)
    with pytest.raises(ValueError, match='summary'):
        data_module().load_comparison()


def test_missing_comparison_fails_clearly(tmp_path):
    with pytest.raises(ValueError, match='archive'):
        data_module().load_comparison(tmp_path)


def test_decision_inspector_preserves_waiting_and_applied_boundary():
    from presentation.adapter import load_replay
    replay = load_replay()
    waiting = data_module().inspect_decision(replay, 11)
    applied = data_module().inspect_decision(replay, 13)
    assert waiting['candidate_khz'] == 4233333
    assert waiting['applied_khz'] == 5100000
    assert waiting['streak'] == 1 and waiting['remaining'] == 2
    assert waiting['transitions'] == 0
    assert applied['remaining'] == 0 and applied['transitions'] == 1
    assert applied['state'] == 'APPLIED'


@pytest.mark.parametrize('tick,delta,want', [(1,-1,1), (34,1,34), (11,1,12), (13,-1,12)])
def test_navigation_bounds(tick, delta, want):
    assert data_module().move_tick(tick, delta, 34) == want


def test_recorded_observations_remain_separate_from_simulated_frequency():
    from presentation.adapter import load_observations
    table = data_module().observation_table(load_observations())
    assert len(table) == 5
    assert 'Applied GHz' not in table.columns
    assert table.iloc[0]['Elapsed seconds'] == pytest.approx(1.1753116990003036)


def test_replay_figure_has_three_aligned_lanes_with_actual_values():
    from presentation.adapter import load_replay
    from daybreak.charts import replay_figure
    replay = load_replay()
    figure = replay_figure(replay, 13)
    traces = {trace.name: trace for trace in figure.data}
    assert list(traces['CPU utilization'].y) == [f.util_pct for f in replay.frames[:13]]
    assert list(traces['Applied simulated frequency'].y)[-1] == pytest.approx(4.233333)
    assert list(traces['Candidate simulated frequency (derived)'].y)[10] == pytest.approx(4.233333)
    assert traces['Candidate simulated frequency (derived)'].line.dash == 'dash'
    assert {trace.xaxis for trace in figure.data} == {'x', 'x2', 'x3'}
    assert all(max(trace.x) <= 13 for trace in figure.data)


def test_unknown_decision_fields_are_displayed_as_unavailable():
    from dataclasses import replace
    from presentation.adapter import load_replay
    replay = load_replay()
    frame = replace(replay.frames[0], candidate_khz=None, streak=None, decision_state='UNAVAILABLE')
    replay = replace(replay, frames=(frame, *replay.frames[1:]))
    info = data_module().inspect_decision(replay, 1)
    assert info['remaining'] is None
    assert info['candidate_khz'] is None


def test_dashboard_import_and_data_loading_do_not_run_live_or_hardware(monkeypatch):
    importlib.import_module('streamlit')  # framework imports are outside the application's boundary
    import subprocess
    import governor
    import monitor.reader
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected process/live/hardware call')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(governor, 'open_setter', forbidden)
    monkeypatch.setattr(monitor.reader, 'sample', forbidden)
    importlib.import_module('daybreak.app')
    data_module().load_comparison()
