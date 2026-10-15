"""Finite playback, rendering and startup safety on Windows and Ubuntu."""
import importlib
import io
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1]


class TerminalStream(io.StringIO):
    encoding = 'utf-8'

    def isatty(self):
        return True


def ui():
    return importlib.import_module('governorlab.app')


def test_playback_emits_all_frames_once_and_never_sleeps_after_last():
    sleeps = []
    frames = list(ui().playback((1, 2, 3), speed=10, clock=lambda: 0, sleep=sleeps.append))
    assert frames == [1, 2, 3]
    assert sleeps == pytest.approx([0.1, 0.2])


@pytest.mark.parametrize('speed', [0, -1, float('nan'), float('inf')])
def test_invalid_playback_speed_is_rejected(speed):
    with pytest.raises(ValueError, match='speed'):
        list(ui().playback((1,), speed=speed))


def test_plain_output_has_all_ticks_summary_and_no_control_sequences():
    output = io.StringIO()
    assert ui().main(['--plain', '--speed', '0.0'], stream=output) == 2
    output = io.StringIO()
    assert ui().main(['--plain', '--instant'], stream=output) == 0
    text = output.getvalue()
    assert 'SYNTHETIC REPLAY' in text
    assert '34/34' in text
    assert '3 simulated transitions' in text
    assert 'VALIDATED REPLAY COMPLETE' in text
    assert 'candidate' in text.lower() and 'WAITING 1/3' in text
    assert '\x1b' not in text


def test_recorded_view_does_not_present_simulated_choices():
    output = io.StringIO()
    assert ui().main(['--recorded-linux', '--plain', '--instant'], stream=output) == 0
    text = output.getvalue()
    assert 'RECORDED LINUX OBSERVATIONS' in text
    assert 'elapsed' in text.lower()
    assert 'No frequency measurements' in text
    assert 'candidate=' not in text
    assert 'simulated transitions' not in text


def test_ascii_fallback_can_write_to_legacy_windows_encoding():
    import codecs
    raw = io.BytesIO()
    stream = codecs.getwriter('ascii')(raw)
    assert ui().main(['--plain', '--instant'], stream=stream) == 0
    assert b'34/34' in raw.getvalue()


def test_ascii_fallback_escapes_unicode_checkout_path_without_losing_metadata(monkeypatch):
    import codecs
    from dataclasses import replace
    from presentation.adapter import load_replay
    data = load_replay()
    unicode_path = 'C:/\u6d4b\u8bd5/ours.csv'
    data = replace(data, metadata={**data.metadata, 'csv_path': unicode_path})
    monkeypatch.setattr(ui(), 'load_replay', lambda: data)
    raw = io.BytesIO()
    assert ui().main(['--plain', '--instant'], stream=codecs.getwriter('ascii')(raw)) == 0
    assert b'VALIDATED REPLAY COMPLETE' in raw.getvalue()
    assert b'\\u6d4b\\u8bd5' in raw.getvalue()
    assert data.metadata['csv_path'] == unicode_path


def test_plain_history_is_progressively_revealed():
    from presentation.adapter import load_replay
    data = load_replay()
    assert len(ui().sparkline(data.frames[:3], unicode=False)) == 3
    assert len(ui().sparkline(data.frames, unicode=False)) == 34
    assert ui().sparkline(data.frames[:3], unicode=False) == '###'


def test_ctrl_c_reports_partial_replay_without_completion_claim(monkeypatch):
    output = io.StringIO()

    def interrupted(frames, **kwargs):
        yield frames[0]
        raise KeyboardInterrupt

    monkeypatch.setattr(ui(), 'playback', interrupted)
    assert ui().main(['--plain'], stream=output) == 130
    assert 'INTERRUPTED' in output.getvalue()
    assert '1/34' in output.getvalue()
    assert 'VALIDATED REPLAY COMPLETE' not in output.getvalue()


def test_rich_frame_shows_progress_graph_and_simulated_decisions():
    pytest.importorskip('rich')
    from rich.console import Console
    from presentation.adapter import load_replay
    data = load_replay()
    output = io.StringIO()
    console = Console(file=output, force_terminal=True, width=100, color_system='truecolor')
    console.print(ui().rich_frame(data, data.frames[:11]))
    text = output.getvalue()
    assert 'Governorlab.' in text
    assert '11/34' in text
    assert 'WAITING 1/3' in text
    assert '4.233' in text and '5.100' in text
    assert 'CPU HISTORY' in text


def test_missing_rich_falls_back_to_plain(monkeypatch):
    monkeypatch.setattr(ui(), 'rich_available', lambda: False)
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 0
    assert '34/34' in output.getvalue()
    assert '\x1b' not in output.getvalue()


def test_rich_startup_finishes_without_refresh_threads(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '100')
    monkeypatch.setenv('LINES', '40')
    monkeypatch.setenv('TERM', 'xterm-256color')
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 0
    text = output.getvalue()
    assert 'Governorlab.' in text
    assert 'FINAL SUMMARY' in text
    assert '34/34' in text
    assert '\x1b' in text


def test_small_terminal_uses_plain_instead_of_clipping(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 0
    assert 'VALIDATED REPLAY COMPLETE' in output.getvalue()
    assert '\x1b' not in output.getvalue()


def test_module_startup_is_bounded_and_read_only():
    result = subprocess.run([sys.executable, '-B', '-m', 'governorlab', '--plain', '--instant'],
                            cwd=ROOT, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'VALIDATED REPLAY COMPLETE' in result.stdout


def test_import_is_silent_and_has_no_process_or_hardware_side_effects():
    code = '''
import subprocess, sys
def forbidden(*args, **kwargs):
    raise AssertionError('process launched at import/startup')
subprocess.Popen = forbidden
import governorlab.app
import presentation.adapter
assert 'fcntl' not in sys.modules
assert 'benchmark.collect_traces' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ''
