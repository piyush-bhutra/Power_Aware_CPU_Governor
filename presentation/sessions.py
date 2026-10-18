"""Shared saved-session store for Governorlab and Daybreak. Reads only; never collects.

Terminal (`governorlab --live`) and dashboard (daybreak worker) captures use the
same on-disk format under run/: capture.csv, metadata.json, decisions.json,
raw_events.jsonl and a session-sha256.json manifest written by collect_live.
"""
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path

from monitor.capture import validate_trace
from presentation.adapter import load_csv, process_live_observations

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'run'
FILES = ('capture.csv', 'metadata.json', 'decisions.json', 'raw_events.jsonl')
MANIFEST = 'session-sha256.json'
MIN_SAMPLES, MAX_SAMPLES, DEFAULT_SAMPLES = 5, 30, 5


def check_sample_count(count):
    if isinstance(count, bool) or not isinstance(count, int) or not MIN_SAMPLES <= count <= MAX_SAMPLES:
        raise ValueError(f'sample count must be an integer from {MIN_SAMPLES} to {MAX_SAMPLES}, got {count!r}')
    return count


def collection_timeout_s(count):
    """Inner collection deadline: about 2 s per one-second sample plus a 2 s margin (5 -> 12 s)."""
    return 2 * check_sample_count(count) + 2


def watchdog_s(count):
    """Parent watchdog: the inner deadline plus 3 s for child startup/teardown (5 -> 15 s)."""
    return collection_timeout_s(count) + 3


def list_sessions(root=RUN):
    """Saved session folders, newest first (folder names start with live-<UTC time>)."""
    root = Path(root)
    # Includes terminal runs and dashboard-owned job subfolders. No arbitrary UI paths.
    candidates = list(root.glob('live-*/metadata.json')) + list(root.glob('daybreak-*/live-*/metadata.json'))
    return sorted((p.parent for p in candidates), key=lambda p: (p.name, p.as_posix()), reverse=True)


def session_hashes(folder):
    return {name: hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest() for name in FILES}


def write_manifest(folder):
    folder = Path(folder)
    temporary = folder / (MANIFEST + '.tmp')
    temporary.write_text(json.dumps(session_hashes(folder)), encoding='utf-8')
    temporary.replace(folder / MANIFEST)


def load_session(folder):
    folder = Path(folder).resolve()
    manifest = folder / MANIFEST
    if manifest.exists():
        hashes = json.loads(manifest.read_text(encoding='utf-8'))
        if set(hashes) != set(FILES) or hashes != session_hashes(folder):
            raise ValueError('Saved session integrity mismatch')
    metadata = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    count = metadata.get('actual_sample_count')
    if (metadata.get('status') != 'validated'
            or isinstance(count, bool) or not isinstance(count, int)
            or not MIN_SAMPLES <= count <= MAX_SAMPLES
            or metadata.get('requested_attempts') != count or metadata.get('generated_load') is not False
            or metadata.get('frequency_control') != 'simulated'
            or metadata.get('observation_source') != 'linux_proc_stat'
            or metadata.get('workload_label') != 'uncontrolled_background'):
        raise ValueError(f'Session is not a validated {MIN_SAMPLES}-{MAX_SAMPLES} interval background capture '
                         'with requested_attempts equal to actual_sample_count')
    rate = metadata.get('expected_jiffies_per_s')
    if not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError('Session CPU accounting rate is unavailable')
    path = folder / 'capture.csv'
    validate_trace(path, count, 'uncontrolled_background', rate)
    records = load_csv(path, 'linux_recorded')
    # Reconstruct with original identity first, permitting portable folder copies.
    data = process_live_observations(records, metadata)
    decisions = json.loads((folder / 'decisions.json').read_text(encoding='utf-8'))
    if decisions != [asdict(frame) for frame in data.frames]:
        raise ValueError('Saved decisions disagree with the existing backend')
    original = metadata['csv_path']
    current = str(path)
    frames = tuple(replace(f, sample_id=f'{current}:{f.tick + 1}') for f in data.frames)
    return replace(data, mode='SAVED LINUX OBSERVATIONS — SIMULATED DECISIONS', frames=frames,
                   metadata={**data.metadata, 'csv_path': current, 'original_csv_path': original,
                             'session_folder': str(folder),
                             'validation': 'Saved raw counters and all decisions revalidated against backend; '
                                           + ('capture hashes checked' if manifest.exists() else 'legacy terminal capture has no hash manifest'),
                             'derived_fields': 'Predicted classes, candidate/applied simulated frequencies and K=3 state use existing backend APIs. '
                                               'This is a saved observation, not a current live feed.'})


def resolve_session(choice, root=RUN):
    """'latest' -> newest saved session under root; otherwise an explicit folder path."""
    if choice == 'latest':
        sessions = list_sessions(root)
        if not sessions:
            raise ValueError(f'No saved sessions under {Path(root)}')
        return sessions[0]
    return Path(choice)
