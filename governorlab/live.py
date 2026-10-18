"""Explicitly invoked, 5-30 attempt background-only collection. No child processes."""
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

from monitor.capture import LABEL_COLS, check_resources, resources, validate_trace
from monitor.reader import log_csv, sample
from presentation.adapter import load_csv, process_live_observations
from presentation.sessions import DEFAULT_SAMPLES, check_sample_count, collection_timeout_s, write_manifest

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'uncontrolled_background'


def expected_jiffies():
    return os.cpu_count() * os.sysconf('SC_CLK_TCK')


@contextmanager
def collection_deadline(seconds=12):
    """Bound synchronous Linux reads/sleeps, restoring process signal state."""
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError('An existing alarm prevents safe live collection')
    previous = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise TimeoutError('Live collection timeout; no automatic retry')
    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def collect_live(output_root=ROOT / 'run', progress=lambda count: None, count=DEFAULT_SAMPLES):
    """Save evidence, validate exactly `count` (5-30) intervals, then simulate decisions.

    Invalid intervals consume attempts, without replacement. Partial/error/interrupt
    sessions retain CSV, observer events and failure metadata and are never replayed.
    Successful sessions get a session-sha256.json manifest: the same on-disk
    format as dashboard (daybreak worker) sessions.
    """
    check_sample_count(count)
    timeout = collection_timeout_s(count)
    if sys.platform != 'linux' or not Path('/proc/stat').is_file():
        raise RuntimeError('Live observation requires Linux /proc/stat')
    initial = resources()
    check_resources(initial, initial)
    rate = expected_jiffies()
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('live-%Y%m%dT%H%M%SZ-'),
                                   dir=output_root))
    csv_path = folder / 'capture.csv'
    metadata = {
        'status': 'collecting', 'started_utc': datetime.now(timezone.utc).isoformat(),
        'csv_path': str(csv_path.resolve()), 'source_commit': 'working-tree',
        'observation_source': 'linux_proc_stat', 'source': '/proc/stat',
        'workload_label': LABEL, 'requested_attempts': count, 'interval_s': 1.0,
        'collection_timeout_s': timeout, 'actual_sample_count': 0, 'observed_intervals_s': [],
        'initial_resources': initial, 'expected_jiffies_per_s': rate,
        'frequency_control': 'simulated', 'generated_load': False,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ('governorlab/live.py', 'governorlab/app.py',
                                       'presentation/adapter.py', 'monitor/reader.py',
                                       'monitor/capture.py', 'classifier/rules.py',
                                       'policy/governor_policy.py', 'setter/freq_setter.py',
                                       'hardware_profile.py')},
    }
    save_json(folder / 'metadata.json', metadata)
    started = time.monotonic()
    try:
        progress(0)
        with collection_deadline(timeout), (folder / 'raw_events.jsonl').open('x', encoding='utf-8') as events:
            def observed(event):
                events.write(json.dumps(event) + '\n')
                events.flush()
                if event.get('event') == 'interval':
                    metadata['observed_intervals_s'].append(event.get('elapsed_s'))
            def annotated():
                source = sample(1.0, count, observer=observed)
                try:
                    for row in source:
                        current = resources()
                        check_resources(current, initial)
                        metadata['last_resources'] = current
                        if not .5 <= row['elapsed_s'] <= 2:
                            raise RuntimeError('Sampling timing anomaly; stopping without retry')
                        yield {**row, **current, 'workload_label': LABEL,
                               'observation_source': 'linux_proc_stat'}
                        metadata['actual_sample_count'] += 1
                        progress(metadata['actual_sample_count'])
                finally:
                    source.close()
            log_csv(str(csv_path), annotated(), LABEL_COLS, mode='x')
            metadata['statistics'] = validate_trace(csv_path, count, LABEL, rate)
            records = load_csv(csv_path, 'linux_recorded')
            # Persist successful actual durations even if an alternate source has
            # no observer events (fixtures); real sampler also preserves invalid attempts.
            metadata['observed_intervals_s'] = [row['elapsed_s'] for row in records]
            data = process_live_observations(records, metadata)
            save_json(folder / 'decisions.json', [asdict(frame) for frame in data.frames])
            metadata.update(status='validated', summary=data.summary)
    except BaseException as error:
        metadata.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                        error=f'{type(error).__name__}: {error}')
        error.live_evidence = str(folder)
        if hasattr(error, 'add_note'):
            error.add_note(f'Live evidence retained at {folder}')
        raise
    finally:
        metadata['finished_utc'] = datetime.now(timezone.utc).isoformat()
        metadata['collection_wall_s'] = time.monotonic() - started
        save_json(folder / 'metadata.json', metadata)
    write_manifest(folder)  # after the final metadata write, so it covers it
    return replace(data, metadata={**data.metadata, **metadata})
