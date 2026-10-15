"""Presentation contracts against preserved evidence, without live sampling."""
import csv
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def adapter():
    return importlib.import_module('presentation.adapter')


def test_archived_replay_preserves_sample_identity_and_configuration():
    data = adapter().load_replay()
    assert len(data.frames) == 34
    assert data.metadata['k'] == 3
    assert data.metadata['seed'] == 11
    assert data.frames[0].sample_id.endswith('ours.csv:2')
    assert data.frames[0].timestamp == 1.0
    assert data.frames[-1].timestamp == 34.0
    assert data.frames[0].util_pct == pytest.approx(95.04950495049505)


def test_replay_is_deterministic_and_matches_archived_backend_outputs():
    first = adapter().load_replay()
    assert first == adapter().load_replay()
    with Path(first.metadata['csv_path']).open(newline='') as stream:
        recorded = list(csv.DictReader(stream))
    assert [f.applied_khz for f in first.frames] == [int(r['target_khz']) for r in recorded]
    assert [f.predicted_class for f in first.frames] == [r['workload_class'] for r in recorded]


def test_candidate_waits_for_three_samples_and_events_exclude_initialization():
    data = adapter().load_replay()
    waiting = data.frames[10:13]
    assert [f.candidate_khz for f in waiting] == [4233333, 4233333, 4233333]
    assert [f.applied_khz for f in waiting] == [5100000, 5100000, 4233333]
    assert [f.streak for f in waiting] == [1, 2, 3]
    assert [f.decision_state for f in waiting] == ['WAITING', 'WAITING', 'APPLIED']
    events = [f.transition for f in data.frames if f.transition]
    assert [e.tick for e in events] == [13, 23, 29]
    assert events[0].previous_khz == 5100000
    assert events[0].new_khz == 4233333
    assert '3 consecutive' in events[0].reason
    assert data.frames[0].transition is None
    assert data.summary['transitions'] == 3
    assert data.summary['class_distribution'] == {'cpu_bound': 10, 'io_bound': 10, 'idle': 6, 'mixed': 8}
    assert data.summary['initial_khz'] == 5100000
    assert data.summary['final_khz'] == 4666667


def test_backend_output_drift_fails_instead_of_displaying_invented_state(monkeypatch):
    from policy.governor_policy import Policy
    monkeypatch.setattr(Policy, 'step', lambda self, sig: self.freqs[0])
    with pytest.raises(ValueError, match='mismatch'):
        adapter().load_replay()


def test_missing_optional_policy_introspection_is_labelled_unavailable():
    from policy.governor_policy import Policy
    original = Policy.step

    # Only exercise a single tick: the changed backend cannot advance its own
    # streak afterward. Adapter state extraction must tolerate unavailable fields.
    policy = Policy([1000, 2000], k=3)
    original(policy, {'util_pct': 90, 'iowait_pct': 0, 'ctxt_per_s': 1,
                      'procs_running': 1, 'procs_blocked': 0})
    policy._streak = None
    state = adapter().policy_snapshot(policy, 'cpu_bound')
    assert state['streak'] is None
    assert state['decision_state'] == 'UNAVAILABLE'


def test_recorded_linux_observations_have_no_synthetic_decision_fields():
    data = adapter().load_observations()
    assert data.mode == 'RECORDED LINUX OBSERVATIONS'
    assert len(data.frames) == 5
    assert data.metadata['validation'] == 'archive hashes and raw-counter validation passed'
    assert data.metadata['source_commit'] == '18b87efa6ffdcc4e7f4ed58936c824876a42d3fc'
    assert data.frames[0].features['elapsed_s'] == pytest.approx(1.1753116990003036)
    for frame in data.frames:
        assert frame.source_kind == 'linux_recorded'
        assert frame.candidate_khz is None
        assert frame.applied_khz is None
        assert frame.predicted_class is None
        assert frame.streak is None
        assert frame.transition is None


@pytest.mark.parametrize('content,kind', [
    ('timestamp,util_pct\n1,50\n', 'synthetic'),
    ('timestamp,util_pct,util_pct\n1,50,50\n', 'synthetic'),
    ('timestamp,util_pct\n1,nan\n', 'linux_recorded'),
])
def test_invalid_or_incomplete_schema_is_rejected(tmp_path, content, kind):
    path = tmp_path / 'bad.csv'
    path.write_text(content)
    with pytest.raises(ValueError):
        adapter().load_csv(path, kind)


def test_archive_tampering_is_rejected(tmp_path):
    (tmp_path / 'SHA256SUMS').write_text('0' * 64 + '  ours.csv\n')
    (tmp_path / 'ours.csv').write_text('changed')
    with pytest.raises(ValueError, match='integrity'):
        adapter().verify_archive(tmp_path)


def test_missing_archive_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match='archive'):
        adapter().load_replay(tmp_path)


def test_current_extended_csv_schema_is_supported_without_mixing_sources(tmp_path):
    from governor import EXTRA_COLS, run
    from monitor.reader import log_csv
    from monitor.synthetic import source
    from policy.governor_policy import Policy
    from setter.freq_setter import SimulatedSetter
    setter = SimulatedSetter([1000, 2000])
    rows = list(run(source([('cpu', 2)]), setter, Policy(setter.freqs)))
    path = tmp_path / 'current.csv'
    log_csv(path, rows, EXTRA_COLS)
    normalized = adapter().load_csv(path, 'synthetic')
    assert len(normalized) == 2
    assert normalized[0]['target_khz'] == 2000
    assert 'raw_prev_user' in normalized[0]
    with pytest.raises(ValueError, match='schema'):
        adapter().load_csv(path, 'linux_recorded')


def test_adapter_import_and_execution_never_select_hardware_or_linux_collectors(monkeypatch):
    import governor
    import monitor.reader
    import setter.freq_setter

    def forbidden(*args, **kwargs):
        raise AssertionError('unsafe operation')

    monkeypatch.setattr(governor, 'open_setter', forbidden)
    monkeypatch.setattr(monitor.reader, 'sample', forbidden)
    monkeypatch.setattr(setter.freq_setter, '_read', forbidden)
    monkeypatch.setattr(setter.freq_setter, '_write', forbidden)
    adapter().load_replay()
    adapter().load_observations()
    assert 'benchmark.collect_traces' not in sys.modules
    assert 'benchmark.safe_cpu_launcher' not in sys.modules
