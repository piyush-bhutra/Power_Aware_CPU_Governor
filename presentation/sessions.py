"""Shared saved-session store for Governorlab and Daybreak. Reads only; never collects.

Terminal (`governorlab --live`) and dashboard (daybreak worker) captures use the
same on-disk format under run/: capture.csv, metadata.json, decisions.json,
raw_events.jsonl and a session-sha256.json manifest written by collect_live.
"""
from collections import Counter
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


def max_attempts(count, strict=False):
    """Strict: exactly `count` attempts. Tolerant: count + max(3, ceil(count/2)) (5 -> 8)."""
    check_sample_count(count)
    return count if strict else count + max(3, -(-count // 2))


def collection_timeout_s(count, strict=False):
    """Inner collection deadline: 2 s per allowed attempt plus 2 s (strict 5 -> 12 s, tolerant 5 -> 18 s)."""
    return 2 * max_attempts(count, strict) + 2


def watchdog_s(count, strict=False):
    """Parent watchdog: the inner deadline plus 3 s for child startup/teardown."""
    return collection_timeout_s(count, strict) + 3


TIMING_QUALITIES = ('clean', 'degraded')
DISCARD_REASONS = {'elapsed_out_of_range': 'measured interval outside 0.5-2 s',
                   'jiffy_ratio_out_of_range': 'CPU accounting rate outside 0.5-1.5x expected',
                   'invalid_counter_interval': 'counters went backwards or did not advance'}


def timing_banner(metadata):
    """Disclosure text for degraded sessions, or None for clean/legacy sessions."""
    if metadata.get('timing_quality') != 'degraded':
        return None
    discarded = metadata.get('discarded_attempts', [])
    reasons = Counter(d.get('reason') for d in discarded)
    detail = ', '.join(f'{n} x {DISCARD_REASONS.get(r, r)}' for r, n in sorted(reasons.items()))
    return (f'{len(discarded)} intervals discarded because of VM timing anomalies ({detail}); '
            f'{metadata.get("attempts_made")} attempts for {metadata.get("actual_sample_count")} kept samples. '
            'Kept samples may be non-adjacent in time.')


def check_timing_fields(metadata, count):
    """Validate tolerant-collection disclosure; legacy sessions without it are 'clean'."""
    if 'timing_quality' not in metadata:
        return dict(timing_quality='clean', discarded_attempts=[], attempts_made=count,
                    kept_attempt_indices=list(range(1, count + 1)))
    quality, discarded = metadata['timing_quality'], metadata.get('discarded_attempts')
    kept, attempts = metadata.get('kept_attempt_indices'), metadata.get('attempts_made')
    if (quality not in TIMING_QUALITIES or not isinstance(discarded, list) or not isinstance(kept, list)
            or len(kept) != count or attempts != count + len(discarded)
            or (quality == 'degraded') != bool(discarded)
            or sorted(kept + [d.get('attempt') for d in discarded]) != list(range(1, attempts + 1))):
        raise ValueError('Session timing disclosure (timing_quality / discarded_attempts / '
                         'kept_attempt_indices / attempts_made) is inconsistent')
    return {}


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
    timing_defaults = check_timing_fields(metadata, count)
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
                   metadata={**data.metadata, **timing_defaults, 'csv_path': current, 'original_csv_path': original,
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
