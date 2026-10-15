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


def rich_frame(data, shown):
    """Build one snapshot; terminal libraries stay outside the shared adapter."""
    from rich import box
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    frame = shown[-1]
    synthetic = frame.source_kind == 'synthetic'
    k = data.metadata.get('k')
    header = Text()
    header.append('Governorlab.', style=f'bold {VIOLET}')
    header.append('  /  Power-Aware CPU Governor\n', style=NEUTRAL)
    header.append(data.mode, style=f'bold {BLUE}')
    header.append(f'    {frame.tick}/{len(data.frames)} samples', style=NEUTRAL)
    if synthetic:
        header.append(f'    K={k}  seed={data.metadata["seed"]}', style=MUTED)
    else:
        header.append('    historical / background only', style=MUTED)
    status = Table.grid(expand=True, padding=(0, 2))
    if synthetic:
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
        detail.append('  |  backend reconstruction checked against archive', style=MUTED)
    else:
        for _ in range(4):
            status.add_column(ratio=1)
        status.add_row('CPU UTILIZATION', 'I/O WAIT', 'CONTEXT SWITCHES', 'ELAPSED INTERVAL')
        status.add_row(f'{frame.util_pct:.3f}%', f'{frame.features["iowait_pct"]:.2f}%',
                       f'{frame.features["ctxt_per_s"]:.1f}/s', f'{frame.features["elapsed_s"]:.4f} s')
        detail = Text('No frequency measurements | no policy reconstruction for this capture', style=AMBER)
    graph = Text(sparkline(shown), style=VIOLET)
    graph.append(f'\n0-100%  |  {len(shown)} revealed samples  |  playback speed is display time', style=MUTED)
    events = [f.transition for f in shown if f.transition]
    if synthetic:
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
                         else 'Recorded observations | not live | no generated workload', style=AMBER))
    return Panel(content, border_style='#596181', padding=(0, 1), style=f'{NEUTRAL} on {BACKGROUND}')


def summary_text(data, shown, interrupted=False):
    synthetic = data.mode == 'SYNTHETIC REPLAY'
    status = 'INTERRUPTED' if interrupted else ('VALIDATED REPLAY COMPLETE' if synthetic else 'RECORDED VIEW COMPLETE')
    lines = [f'{status} | {len(shown)}/{len(data.frames)} samples']
    if synthetic:
        transitions = sum(f.transition is not None for f in shown)
        distribution = dict(Counter(f.predicted_class for f in shown))
        final = shown[-1].applied_khz if shown else data.metadata['initial_khz']
        lines += [f'{transitions} simulated transitions | initial {ghz(data.metadata["initial_khz"])} | final {ghz(final)}',
                  f'K={data.metadata["k"]} | classes: ' + ', '.join(f'{k}={v}' for k, v in distribution.items()),
                  'Candidate and persistence fields are derived with the existing backend; applied outputs match the archive.']
    elif shown:
        lines += [f'Mean CPU {sum(f.util_pct for f in shown) / len(shown):.4f}% | '
                  f'mean elapsed {sum(f.features["elapsed_s"] for f in shown) / len(shown):.4f} s']
    lines += [f'Source: {data.metadata["csv_path"]}', f'Producing source commit: {data.metadata["source_commit"]}',
              f'Validation: {data.metadata["validation"]}', data.metadata['limitations']]
    return '\n'.join(lines)


def plain_tick(data, frame):
    prefix = f'{frame.tick:02d}/{len(data.frames)} | CPU {frame.util_pct:5.1f}%'
    if frame.source_kind == 'synthetic':
        return (f'{prefix} | {frame.predicted_class:<9} | candidate={ghz(frame.candidate_khz)} '
                f'| simulated={ghz(frame.applied_khz)} | {state_label(frame, data.metadata["k"])}')
    return (f'{prefix} | iowait={frame.features["iowait_pct"]:.2f}% '
            f'| ctxt={frame.features["ctxt_per_s"]:.1f}/s | elapsed={frame.features["elapsed_s"]:.4f}s')


def _can_render(stream):
    encoding = getattr(stream, 'encoding', None) or 'ascii'
    try:
        '\u2581\u2500'.encode(encoding)
    except (UnicodeError, LookupError):
        return False
    return bool(getattr(stream, 'isatty', lambda: False)()) and os.environ.get('TERM') != 'dumb'


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
    parser.add_argument('--recorded-linux', action='store_true', help='show five archived Linux observations; no live sampling')
    parser.add_argument('--speed', type=float, default=4, help='presentation ticks/second, 2-60 (default 4)')
    parser.add_argument('--instant', action='store_true', help='finish with no playback delay')
    parser.add_argument('--plain', action='store_true', help='portable ASCII output, no terminal control codes or Rich dependency')
    try:
        args = parser.parse_args(argv)
        if not math.isfinite(args.speed) or not 2 <= args.speed <= 60:
            parser.error('--speed must be between 2 and 60 ticks per second')
    except SystemExit as error:
        return error.code
    shown = []
    try:
        data = load_observations() if args.recorded_linux else load_replay()
        use_rich = not args.plain and _can_render(stream) and rich_available()
        if use_rich:
            from rich.console import Console
            from rich.live import Live
            console = Console(file=stream, highlight=False)
            final_height = len(console.render_lines(rich_frame(data, data.frames), console.options))
            if console.width < 72 or console.height < final_height:
                use_rich = False
        if use_rich:
            with Live(console=console, auto_refresh=False, transient=False,
                      redirect_stdout=False, redirect_stderr=False) as live:
                for frame in playback(data.frames, speed=args.speed, instant=args.instant):
                    shown.append(frame)
                    live.update(rich_frame(data, shown), refresh=True)
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
    except KeyboardInterrupt:
        if 'data' in locals():
            write_line(stream, '\n' + summary_text(data, shown, interrupted=True))
        else:
            write_line(stream, '\nINTERRUPTED before archive validation completed')
        return 130
    except (OSError, ValueError, KeyError, TypeError) as error:
        write_line(stream, f'Governorlab could not validate/display the archive: {error}')
        return 1
