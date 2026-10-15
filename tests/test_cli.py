"""CLI regressions: bounded synthetic output and hardware-independent execution."""
import csv
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import governor


@pytest.mark.parametrize('ticks, expected', [(3, 3), (0, 0), (30, 20)])
def test_synthetic_tick_limit_in_csv(tmp_path, ticks, expected):
    output = tmp_path / 'run.csv'
    result = subprocess.run(
        [sys.executable, 'governor.py', '--synthetic', '--ticks', str(ticks),
         '--csv', str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    with output.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == expected


def test_synthetic_never_probes_hardware(monkeypatch, capsys):
    def forbidden_probe(*args, **kwargs):
        pytest.fail('Synthetic execution must not probe or select a hardware setter')

    monkeypatch.setattr(governor, 'open_setter', forbidden_probe)
    monkeypatch.setattr(sys, 'argv', ['governor.py', '--synthetic', '--ticks', '1'])
    governor.main()
    output = capsys.readouterr().out
    assert 'SIMULATED' in output
    assert len([line for line in output.splitlines() if 'W (est)' in line]) == 1


def test_negative_ticks_rejected_before_hardware_probe(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['governor.py', '--synthetic', '--ticks', '-1'])
    with pytest.raises(SystemExit) as error:
        governor.main()
    assert error.value.code == 2


def test_review_demo_generates_evidence(tmp_path):
    import json

    result = subprocess.run(
        [sys.executable, '-m', 'benchmark.review_demo', '--outdir', str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    metadata = json.loads((tmp_path / 'metadata.json').read_text())
    assert metadata['inputs'] == 'synthetic'
    assert metadata['frequency_control'] == 'simulated'
    assert metadata['power_energy'] == 'modelled'
    with (tmp_path / 'ours.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 34
    assert {r['workload_class'] for r in rows} == {'cpu_bound', 'io_bound', 'idle', 'mixed'}
    for name in ('synthetic_modelled_energy.png', 'synthetic_simulated_frequency.png'):
        assert (tmp_path / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
