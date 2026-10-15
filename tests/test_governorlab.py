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


def test_undersized_terminal_uses_plain_instead_of_clipping(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '40')
    monkeypatch.setenv('LINES', '12')
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
import os, subprocess, sys
# subprocess legitimately imports fcntl on Linux. Snapshot stdlib imports first.
stdlib_modules = set(sys.modules)
unsafe_modules = ('benchmark.collect_traces', 'benchmark.safe_cpu_launcher',
                  'benchmark.background_launcher')
def forbidden(*args, **kwargs):
    raise AssertionError('unsafe process or hardware operation')
def guard(event, args):
    if event == 'import' and args[0] in unsafe_modules:
        raise AssertionError('unsafe collector or launcher import')
    if event in ('subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn'):
        forbidden()
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.fsdecode(args[0]).replace('\\\\', '/')
        if path.startswith(('/proc/', '/sys/')):
            forbidden()
sys.addaudithook(guard)
subprocess.Popen = forbidden
os.system = forbidden
import governorlab.app
import presentation.adapter
assert 'fcntl' not in set(sys.modules) - stdlib_modules
assert not set(unsafe_modules).intersection(sys.modules)
'''
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ''


@pytest.mark.parametrize('width,height', [(80, 24), (80, 25), (100, 30)])
def test_default_interactive_command_uses_visual_dashboard_at_normal_sizes(monkeypatch, width, height):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', str(width))
    monkeypatch.setenv('LINES', str(height))
    monkeypatch.setenv('TERM', 'dumb')
    monkeypatch.setattr(ui().sys, 'platform', 'win32')
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 0
    text = output.getvalue()
    assert 'FINAL SUMMARY' in text
    assert '\x1b' in text
    assert '01/34 | CPU' not in text
    assert '3 simulated transitions' in text


def test_redirected_output_explains_plain_fallback():
    output = io.StringIO()
    assert ui().main(['--instant'], stream=output) == 0
    assert 'Plain output: stdout is not an interactive terminal' in output.getvalue()


def test_visual_flag_rejects_redirected_output_without_dumping_ticks():
    output = io.StringIO()
    assert ui().main(['--visual', '--instant'], stream=output) == 2
    assert 'Visual mode unavailable' in output.getvalue()
    assert '01/34' not in output.getvalue()


def test_missing_rich_is_explained_and_explicit_rich_mode_fails(monkeypatch):
    monkeypatch.setattr(ui(), 'rich_available', lambda: False)
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 0
    assert 'Rich is not installed' in output.getvalue()
    output = TerminalStream()
    assert ui().main(['--rich', '--instant'], stream=output) == 2
    assert 'requirements-terminal.txt' in output.getvalue()


def test_visual_interrupt_restores_cursor_and_preserves_partial_summary(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    monkeypatch.setenv('TERM', 'xterm-256color')
    output = TerminalStream()
    def interrupted(frames, **kwargs):
        yield frames[0]
        raise KeyboardInterrupt
    monkeypatch.setattr(ui(), 'playback', interrupted)
    assert ui().main(['--visual'], stream=output) == 130
    text = output.getvalue()
    assert 'INTERRUPTED' in text and '1/34' in text
    assert '\x1b[?25h' in text
    assert 'VALIDATED REPLAY COMPLETE' not in text


def test_renderer_errors_are_reported_without_plain_replay(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '100')
    monkeypatch.setenv('LINES', '40')
    monkeypatch.setenv('TERM', 'xterm-256color')
    def broken(*args, **kwargs):
        raise RuntimeError('renderer probe failure')
    monkeypatch.setattr(ui(), 'rich_frame', broken)
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 1
    assert 'renderer probe failure' in output.getvalue()
    assert '01/34 | CPU' not in output.getvalue()


def test_compact_frame_keeps_all_policy_fields_and_history_visible():
    pytest.importorskip('rich')
    from rich.console import Console
    from presentation.adapter import load_replay
    data = load_replay()
    console = Console(width=80, height=24, file=io.StringIO(), force_terminal=True,
                      legacy_windows=False, color_system='truecolor')
    renderable = ui().rich_frame(data, data.frames, compact=True)
    lines = console.render_lines(renderable, console.options)
    assert len(lines) <= 24
    console.print(renderable)
    text = console.file.getvalue()
    for expected in ('CPU', 'mixed', 'Candidate', 'Applied', 'CPU HISTORY', 'TRANSITIONS', '13', '23', '29', 'simulated'):
        assert expected in text


def test_explicit_visual_enables_colors_without_changing_environment(monkeypatch):
    pytest.importorskip('rich')
    from presentation.adapter import load_replay
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('NO_COLOR', '1')
    import os
    console, compact, reason = ui().select_renderer(load_replay(), TerminalStream(), visual=True)
    assert console is not None and not console.no_color
    assert os.environ['NO_COLOR'] == '1'
    assert os.environ['TERM'] == 'xterm-256color'


def test_default_honors_no_color_but_explains_monochrome_visual_mode(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('NO_COLOR', '1')
    output = TerminalStream()
    assert ui().main(['--instant'], stream=output) == 0
    assert 'colors disabled by NO_COLOR' in output.getvalue()
    assert 'FINAL SUMMARY' in output.getvalue()


def test_interactive_legacy_encoding_uses_visual_ascii_graph(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    monkeypatch.setenv('TERM', 'xterm-256color')
    class LegacyStream(TerminalStream):
        encoding = 'cp1252'
    output = LegacyStream()
    assert ui().main(['--visual', '--instant'], stream=output) == 0
    text = output.getvalue()
    assert 'FINAL SUMMARY' in text
    assert '01/34 | CPU' not in text
    text.encode('cp1252')


def test_linux_dumb_terminal_is_not_overridden(monkeypatch):
    pytest.importorskip('rich')
    monkeypatch.setattr(ui().sys, 'platform', 'linux')
    monkeypatch.setenv('TERM', 'dumb')
    output = TerminalStream()
    assert ui().main(['--visual', '--instant'], stream=output) == 2
    assert 'check TERM/TTY' in output.getvalue()


def test_plain_does_not_require_rich_even_on_an_interactive_console(monkeypatch):
    def unavailable_probe():
        raise AssertionError('Explicit plain must not probe Rich')
    monkeypatch.setattr(ui(), 'rich_available', unavailable_probe)
    output = TerminalStream()
    assert ui().main(['--plain', '--instant'], stream=output) == 0
    assert '01/34 | CPU' in output.getvalue()
    assert '\x1b' not in output.getvalue()
