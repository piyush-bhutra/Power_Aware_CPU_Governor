"""Governorlab terminal UI. Playback time is presentation time, never measurement time."""
import argparse
from collections import Counter
import importlib.util
import math
import os
import sys
import time

from presentation.adapter import load_observations, load_replay

VIOLET = '#bda6ff'
BLUE = '#8ed6ff'
AMBER = '#f5c779'
GREEN = '#a5e2b0'
NEUTRAL = '#d7dce7'
MUTED = '#969fb2'
BACKGROUND = '#10131e'


def playback(frames, speed=4.0, instant=False, clock=time.monotonic, sleep=time.sleep):
    """Yield a finite sequence against monotonic deadlines, without a refresh thread."""
    if not math.isfinite(speed) or not 2 <= speed <= 60:
        raise ValueError('speed must be between 2 and 60 ticks per second')
    start = clock()
    for index, frame in enumerate(frames):
        if index and not instant:
            remaining = start + index / speed - clock()
            if remaining > 0:
                sleep(remaining)
        yield frame


def rich_available():
    return importlib.util.find_spec('rich') is not None


def ghz(value):
    return f'{value / 1_000_000:.3f} GHz' if value is not None else 'unavailable'


def state_label(frame, k):
    if frame.decision_state == 'WAITING':
        return f'WAITING {frame.streak}/{k}'
    if frame.decision_state == 'STABLE':
        return f'STABLE | streak {frame.streak} (K={k} met)'
    if frame.decision_state == 'APPLIED':
        return f'APPLIED | {frame.streak}/{k} persistence met'
    return 'Decision state unavailable'


def sparkline(frames, width=60, unicode=True):
    values = [f.util_pct for f in frames][-width:]
    levels = '..:-=+*#@' if not unicode else '\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588'
    return ''.join(levels[min(len(levels) - 1, int(v / 100 * (len(levels) - 1)))] for v in values)


def rich_frame(data, shown, *, compact=False, unicode=True):
    """Build one snapshot; terminal libraries stay outside the shared adapter."""
    from rich import box
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    if compact:
        return compact_frame(data, shown, unicode=unicode)
    frame = shown[-1]
    synthetic = frame.source_kind == 'synthetic'
    live_session = frame.source_kind == 'linux_live'
    decisions = synthetic or live_session
    k = data.metadata.get('k')
    header = Text()
    header.append('Governorlab.', style=f'bold {VIOLET}')
    header.append('  /  Power-Aware CPU Governor\n', style=NEUTRAL)
    header.append(data.mode, style=f'bold {BLUE}')
    header.append(f'    {frame.tick}/{len(data.frames)} samples', style=NEUTRAL)
    if synthetic:
        header.append(f'    K={k}  seed={data.metadata["seed"]}', style=MUTED)
    elif live_session:
        header.append('    K=3 / fresh background', style=MUTED)
    else:
        header.append('    historical / background only', style=MUTED)
    status = Table.grid(expand=True, padding=(0, 2))
    if decisions:
        for _ in range(4):
            status.add_column(ratio=1)
        status.add_row(Text('CPU UTILIZATION', style=MUTED), Text('PREDICTED CLASS', style=MUTED),
                       Text('CANDIDATE / DERIVED', style=MUTED), Text('APPLIED / SIMULATED', style=MUTED))
        status.add_row(Text(f'{frame.util_pct:5.1f}%', style=f'bold {VIOLET}'),
                       Text(frame.predicted_class, style=f'bold {NEUTRAL}'),
                       Text(ghz(frame.candidate_khz), style=f'bold {VIOLET}'),
                       Text(ghz(frame.applied_khz), style=f'bold {BLUE}'))
        state_color = AMBER if frame.decision_state == 'WAITING' else GREEN
        detail = Text(state_label(frame, k), style=state_color)
        detail.append('  |  measured inputs / existing backend' if live_session else
                      '  |  backend reconstruction checked against archive', style=MUTED)
    else:
        for _ in range(4):
            status.add_column(ratio=1)
        status.add_row('CPU UTILIZATION', 'I/O WAIT', 'CONTEXT SWITCHES', 'ELAPSED INTERVAL')
        status.add_row(f'{frame.util_pct:.3f}%', f'{frame.features["iowait_pct"]:.2f}%',
                       f'{frame.features["ctxt_per_s"]:.1f}/s', f'{frame.features["elapsed_s"]:.4f} s')
        detail = Text('No frequency measurements | no policy reconstruction for this capture', style=AMBER)
    graph = Text(sparkline(shown, unicode=unicode), style=VIOLET)
    graph.append(f'\n0-100%  |  {len(shown)} revealed samples  |  playback speed is display time', style=MUTED)
    events = [f.transition for f in shown if f.transition]
    if decisions:
        history = Table(box=box.SIMPLE, expand=True, padding=(0, 1))
        for label in ('TICK', 'SIMULATED CHANGE', 'WORKLOAD', 'VERIFIED REASON'):
            history.add_column(label, style=NEUTRAL, header_style=MUTED)
        for event in events[-4:]:
            history.add_row(str(event.tick), f'{ghz(event.previous_khz)} -> {ghz(event.new_khz)}',
                            event.predicted_class, event.reason)
        if not events:
            history.add_row('--', 'No applied changes yet', '--', 'Initialization is not a transition')
        lower = Panel(history, title='APPLIED TRANSITIONS / SIMULATED', border_style='#40485e')
        feature_text = Text(f'I/O wait {frame.features["iowait_pct"]:.1f}%   '
                            f'context switches {frame.features["ctxt_per_s"]:.0f}/s   '
                            f'runnable {frame.features["procs_running"]}   blocked {frame.features["procs_blocked"]}', style=MUTED)
    else:
        feature_text = Text('Source: linux_proc_stat | validation: archive + raw counters passed', style=GREEN)
        lower = Text('Original observation timestamps and measured elapsed intervals are preserved.', style=MUTED)
    content = Group(header, Text(''), status, Text(''), detail, feature_text,
                    Panel(graph, title='CPU HISTORY / PROGRESSIVE', border_style='#40485e'), lower,
                    Text(f'Source: {data.metadata["source_commit"][:12]} | {data.metadata["csv_path"].replace(chr(92), "/").split("/review1/")[-1]}', style=MUTED),
                    Text('Invented inputs | simulated frequency | provisional thresholds' if synthetic
                         else ('Measured Linux | simulated decisions | no generated load' if live_session
                               else 'Recorded observations | not live | no generated workload'), style=AMBER))
    return Panel(content, border_style='#596181', padding=(0, 1), style=f'{NEUTRAL} on {BACKGROUND}')


def compact_frame(data, shown, *, unicode=True):
    """Keep the complete replay dashboard within a normal 80x24 terminal."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    frame = shown[-1]
    synthetic = frame.source_kind == 'synthetic'
    live_session = frame.source_kind == 'linux_live'
    decisions = synthetic or live_session
    k = data.metadata.get('k')
    heading = Text('Governorlab.  /  Power-Aware CPU Governor', style=f'bold {VIOLET}')
    mode = Text(f'{data.mode}  {frame.tick}/{len(data.frames)}', style=BLUE)
    mode.append(f'  |  K={k}  seed={data.metadata["seed"]}' if synthetic else ('  |  K=3 / fresh background' if live_session else '  |  historical background'), style=MUTED)
    metrics = Table.grid(expand=True, padding=(0, 1))
    for _ in range(4):
        metrics.add_column(ratio=1)
    if decisions:
        metrics.add_row(Text('CPU util', style=MUTED), Text('Class', style=MUTED),
                        Text('Candidate*', style=MUTED), Text('Applied (sim.)', style=MUTED))
        metrics.add_row(Text(f'{frame.util_pct:.1f}%', style=f'bold {VIOLET}'),
                        Text(frame.predicted_class, style=NEUTRAL),
                        Text(ghz(frame.candidate_khz), style=VIOLET), Text(ghz(frame.applied_khz), style=BLUE))
        detail = Text(state_label(frame, k), style=AMBER if frame.decision_state == 'WAITING' else GREEN)
    else:
        metrics.add_row('CPU util', 'I/O wait', 'Switches/s', 'Elapsed')
        metrics.add_row(f'{frame.util_pct:.3f}%', f'{frame.features["iowait_pct"]:.2f}%',
                        f'{frame.features["ctxt_per_s"]:.1f}', f'{frame.features["elapsed_s"]:.4f} s')
        detail = Text('No frequency measurements; no simulated decisions', style=AMBER)
    features = Text(f'I/O {frame.features["iowait_pct"]:.1f}% | ctxt {frame.features["ctxt_per_s"]:.0f}/s | '
                    f'run {frame.features["procs_running"]} | blocked {frame.features["procs_blocked"]}', style=MUTED)
    policy = Panel(Group(metrics, detail, features), title='POLICY / SIMULATED' if decisions else 'RECORDED COUNTERS',
                   border_style=BLUE, padding=(0, 1))
    graph = Panel(Group(Text(sparkline(shown, width=34, unicode=unicode), style=VIOLET),
                        Text('0-100% | revealed samples only | display-time playback', style=MUTED)),
                  title='CPU HISTORY', border_style=VIOLET, padding=(0, 1))
    if decisions:
        events = [f.transition for f in shown if f.transition]
        table = Table(box=None, expand=True, padding=(0, 1))
        for label in ('Tick', 'Simulated GHz', 'Class', 'Reason*'):
            table.add_column(label, header_style=MUTED)
        for event in events[-3:]:
            reason = f'K={k} met' if 'consecutive' in event.reason else 'unavailable'
            table.add_row(str(event.tick), f'{event.previous_khz / 1_000_000:.3f} -> {event.new_khz / 1_000_000:.3f}',
                          event.predicted_class, reason)
        if not events:
            table.add_row('--', 'No changes yet', '--', 'initialization excluded')
        lower = Panel(table, title=f'TRANSITIONS / SIMULATED ({len(events)})', border_style='#596181', padding=(0, 1))
        note = ('Measured features -> classifier -> Policy -> SimulatedSetter' if live_session
                else '*Derived with backend; applied outputs match archive')
        limits = ('Measured Linux | simulated frequency | provisional rules' if live_session
                  else 'Synthetic inputs | simulated frequency | provisional rules')
    else:
        lower = Text('Validation: archive hashes + raw counters passed', style=GREEN)
        note = 'Historical observations, not live or idle ground truth'
        limits = 'No loaded-stability, accuracy or physical-savings claim'
    footer = Text(f'Source {data.metadata["source_commit"][:12]} | {note}', style=MUTED)
    return Group(heading, mode, policy, graph, lower, footer, Text(limits, style=AMBER))


def summary_text(data, shown, interrupted=False):
    synthetic = data.mode == 'SYNTHETIC REPLAY'
    live_session = data.mode.startswith('LIVE LINUX')
    status = 'INTERRUPTED' if interrupted else ('LIVE SESSION COMPLETE' if live_session else ('VALIDATED REPLAY COMPLETE' if synthetic else 'RECORDED VIEW COMPLETE'))
    lines = [f'{status} | {len(shown)}/{len(data.frames)} samples']
    if synthetic or live_session:
        transitions = sum(f.transition is not None for f in shown)
        distribution = dict(Counter(f.predicted_class for f in shown))
        final = shown[-1].applied_khz if shown else data.metadata['initial_khz']
        lines += [f'{transitions} simulated transitions | initial {ghz(data.metadata["initial_khz"])} | final {ghz(final)}',
                  f'K={data.metadata["k"]} | classes: ' + ', '.join(f'{k}={v}' for k, v in distribution.items()),
                  ('Measured Linux counters -> derived features -> predicted classes -> simulated decisions.' if live_session else
                   'Candidate and persistence fields are derived with the existing backend; applied outputs match the archive.')]
        if live_session:
            lines += ['Predicted classes use provisional rules; candidates and applied frequencies are simulated.',
                      'Physical power/energy and completion time unavailable.',
                      f'Observed CPU frequency available: {data.metadata["measured_frequency_samples"]}/{len(data.frames)} samples.']
            if shown:
                lines += [f'Mean CPU {sum(f.util_pct for f in shown) / len(shown):.4f}% | '
                          f'I/O wait {sum(f.features["iowait_pct"] for f in shown) / len(shown):.4f}% | '
                          f'context switches {sum(f.features["ctxt_per_s"] for f in shown) / len(shown):.1f}/s',
                          f'Mean measured interval {sum(f.features["elapsed_s"] for f in shown) / len(shown):.4f} s']
    elif shown:
        lines += [f'Mean CPU {sum(f.util_pct for f in shown) / len(shown):.4f}% | '
                  f'mean elapsed {sum(f.features["elapsed_s"] for f in shown) / len(shown):.4f} s']
    lines += [f'Source: {data.metadata["csv_path"]}', f'Producing source commit: {data.metadata["source_commit"]}',
              f'Validation: {data.metadata["validation"]}', data.metadata['limitations']]
    return '\n'.join(lines)


def plain_tick(data, frame):
    prefix = f'{frame.tick:02d}/{len(data.frames)} | CPU {frame.util_pct:5.1f}%'
    if frame.source_kind in ('synthetic', 'linux_live'):
        return (f'{prefix} | {frame.predicted_class:<9} | candidate={ghz(frame.candidate_khz)} '
                f'| simulated={ghz(frame.applied_khz)} | {state_label(frame, data.metadata["k"])}')
    return (f'{prefix} | iowait={frame.features["iowait_pct"]:.2f}% '
            f'| ctxt={frame.features["ctxt_per_s"]:.1f}/s | elapsed={frame.features["elapsed_s"]:.4f}s')


def _supports_unicode(stream):
    encoding = getattr(stream, 'encoding', None) or 'ascii'
    try:
        '\u2581\u2500'.encode(encoding)
    except (UnicodeError, LookupError):
        return False
    return True


def select_renderer(data, stream, plain=False, visual=False):
    """Return console/layout or an explicit fallback reason; never hide errors."""
    if plain:
        return None, False, ''
    try:
        tty = bool(getattr(stream, 'isatty', lambda: False)())
    except (OSError, ValueError):
        tty = False
    if not tty:
        return None, False, 'stdout is not an interactive terminal; run in Windows PowerShell or an Ubuntu terminal'
    if not rich_available():
        return None, False, 'Rich is not installed; install requirements-terminal.txt in this environment'
    from rich.console import Console
    environment = dict(os.environ)
    # Windows capability comes from its console API. An inherited POSIX TERM=dumb
    # must not disable a working Windows console or Rich Live's cursor updates.
    if sys.platform == 'win32' and environment.get('TERM', '').lower() in ('dumb', 'unknown'):
        environment['TERM'] = 'xterm-256color'
    console = Console(file=stream, highlight=False, _environ=environment,
                      no_color=False if visual else None)
    if not console.is_terminal or not console.is_interactive or console.is_dumb_terminal:
        return None, False, 'console does not support interactive cursor updates (check TERM/TTY settings)'
    unicode = _supports_unicode(stream)
    full = rich_frame(data, data.frames, unicode=unicode)
    full_height = len(console.render_lines(full, console.options))
    compact = console.width < 100 or full_height > console.height
    if compact:
        renderable = rich_frame(data, data.frames, compact=True, unicode=unicode)
        height = len(console.render_lines(renderable, console.options))
        if console.width < 60 or height > console.height:
            return None, False, f'terminal {console.width}x{console.height} is too small; enlarge to at least 80x24'
    return console, compact, ''


def write_line(stream, text, flush=False):
    """Escape unsupported path/message characters without altering source metadata."""
    encoding = getattr(stream, 'encoding', None) or 'ascii'
    safe = str(text).encode(encoding, errors='backslashreplace').decode(encoding)
    stream.write(safe + '\n')
    if flush:
        stream.flush()


def main(argv=None, stream=None):
    stream = stream if stream is not None else sys.stdout
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--live', action='store_true', help='collect five fresh Linux intervals, then replay simulated decisions')
    sources.add_argument('--recorded-linux', action='store_true', help='show five archived Linux observations; no live sampling')
    parser.add_argument('--speed', type=float, default=4, help='presentation ticks/second, 2-60 (default 4)')
    parser.add_argument('--instant', action='store_true', help='finish with no playback delay')
    renderer = parser.add_mutually_exclusive_group()
    renderer.add_argument('--plain', action='store_true', help='portable ASCII output, no terminal control codes or Rich dependency')
    renderer.add_argument('--visual', '--rich', dest='visual', action='store_true',
                          help='require Rich Live; report why unavailable rather than print plain ticks')
    try:
        args = parser.parse_args(argv)
        if not math.isfinite(args.speed) or not 2 <= args.speed <= 60:
            parser.error('--speed must be between 2 and 60 ticks per second')
    except SystemExit as error:
        return error.code
    shown = []
    try:
        if args.live:
            # Probe terminal readiness before performing any live sampling.
            preview = load_replay()
            console, compact, reason = select_renderer(preview, stream, plain=args.plain, visual=args.visual)
            if args.visual and console is None:
                write_line(stream, f'Visual mode unavailable: {reason}')
                return 2
            from governorlab.live import collect_live
            data = collect_live(progress=lambda n: write_line(stream, f'Collecting Linux samples: {n}/5', flush=True))
        else:
            data = load_observations() if args.recorded_linux else load_replay()
        console, compact, reason = select_renderer(data, stream, plain=args.plain, visual=args.visual)
        use_rich = console is not None
        if args.visual and not use_rich:
            write_line(stream, f'Visual mode unavailable: {reason}')
            return 2
        if not use_rich and reason:
            write_line(stream, f'Plain output: {reason}')
        if use_rich:
            if console.no_color:
                write_line(stream, 'Rich Live: colors disabled by NO_COLOR; use --visual to enable dashboard colors')
            from rich.live import Live
            with Live(console=console, auto_refresh=False, transient=False,
                      redirect_stdout=False, redirect_stderr=False) as live:
                for frame in playback(data.frames, speed=args.speed, instant=args.instant):
                    shown.append(frame)
                    live.update(rich_frame(data, shown, compact=compact, unicode=_supports_unicode(stream)), refresh=True)
        else:
            write_line(stream, f'Governorlab. / Power-Aware CPU Governor\n{data.mode}')
            if data.mode == 'SYNTHETIC REPLAY':
                write_line(stream, f'K={data.metadata["k"]} | seed={data.metadata["seed"]} | inputs synthetic / frequency simulated')
            for frame in playback(data.frames, speed=args.speed, instant=args.instant):
                shown.append(frame)
                write_line(stream, plain_tick(data, frame) + ' | ' + sparkline(shown, unicode=False), flush=True)
                if frame.transition:
                    event = frame.transition
                    write_line(stream, f'  TRANSITION {event.tick}: {ghz(event.previous_khz)} -> {ghz(event.new_khz)} | {event.reason}')
            write_line(stream, 'CPU history: ' + sparkline(shown, unicode=False))
        text = summary_text(data, shown)
        if use_rich:
            from rich.panel import Panel
            from rich.text import Text
            console.print(Panel(Text(text), title='FINAL SUMMARY', border_style=GREEN))
        else:
            write_line(stream, '\n' + text)
        return 0
    except KeyboardInterrupt as error:
        if 'data' in locals():
            write_line(stream, '\n' + summary_text(data, shown, interrupted=True))
        else:
            write_line(stream, '\nINTERRUPTED before observation validation completed' +
                       (f'; evidence retained at {error.live_evidence}' if hasattr(error, 'live_evidence') else ''))
        return 130
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        write_line(stream, f'Governorlab could not collect/validate/display the session: {error}')
        if hasattr(error, 'live_evidence'):
            write_line(stream, f'Live evidence retained at {error.live_evidence}')
        return 1
