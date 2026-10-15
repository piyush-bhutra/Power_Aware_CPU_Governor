"""Read and revalidate saved Governorlab live captures, without collection."""
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


def list_sessions(root=RUN):
    root = Path(root)
    # Includes terminal runs and dashboard-owned job subfolders. No arbitrary UI paths.
    candidates = list(root.glob('live-*/metadata.json')) + list(root.glob('daybreak-*/live-*/metadata.json'))
    return sorted((p.parent for p in candidates), key=lambda p: p.as_posix(), reverse=True)


def session_hashes(folder):
    return {name: hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest() for name in FILES}


def load_session(folder):
    folder = Path(folder).resolve()
    manifest = folder / 'session-sha256.json'
    if manifest.exists():
        hashes = json.loads(manifest.read_text(encoding='utf-8'))
        if set(hashes) != set(FILES) or hashes != session_hashes(folder):
            raise ValueError('Saved session integrity mismatch')
    metadata = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    if (metadata.get('status') != 'validated' or metadata.get('actual_sample_count') != 5
            or metadata.get('requested_attempts') != 5 or metadata.get('generated_load') is not False
            or metadata.get('frequency_control') != 'simulated'
            or metadata.get('observation_source') != 'linux_proc_stat'
            or metadata.get('workload_label') != 'uncontrolled_background'):
        raise ValueError('Session is not a validated five-interval background capture')
    rate = metadata.get('expected_jiffies_per_s')
    if not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError('Session CPU accounting rate is unavailable')
    path = folder / 'capture.csv'
    validate_trace(path, 5, 'uncontrolled_background', rate)
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
