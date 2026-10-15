"""Normalize archived observations and verify replay with the existing backend.

No terminal imports, live sampling, collectors, subprocesses or hardware selection.
Private policy state is read only for derived display fields; outputs must match
the archived run before any reconstructed state is offered to a presentation.
"""
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from governor import run
from monitor.capture import validate_trace
from monitor.synthetic import source
from policy.governor_policy import Policy
from setter.freq_setter import SimulatedSetter

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence' / 'review1'
SYNTHETIC_ARCHIVE = EVIDENCE / 'synthetic_policy_comparison_20261015'
LINUX_ARCHIVE = EVIDENCE / 'background_readiness_20261015'
FEATURES = ('iowait_pct', 'irq_pct', 'ctxt_per_s', 'procs_running',
            'procs_blocked', 'iowait_over_util', 'ctxt_over_run', 'elapsed_s')
INTEGER_FIELDS = {'procs_running', 'procs_blocked', 'freq_khz', 'target_khz', 'requested_khz'}
NUMERIC_FIELDS = {'timestamp', 'util_pct', 'est_power_w', *FEATURES, *INTEGER_FIELDS}


@dataclass(frozen=True)
class Transition:
    tick: int
    previous_khz: int
    new_khz: int
    predicted_class: str
    reason: str


@dataclass(frozen=True)
class Frame:
    tick: int
    sample_id: str
    timestamp: float
    util_pct: float
    features: dict
    source_kind: str
    predicted_class: str | None = None
    candidate_khz: int | None = None
    applied_khz: int | None = None
    pending_class: str | None = None
    streak: int | None = None
    stable_class: str | None = None
    decision_state: str = 'UNAVAILABLE'
    transition: Transition | None = None


@dataclass(frozen=True)
class Dataset:
    mode: str
    frames: tuple[Frame, ...]
    metadata: dict

    @property
    def summary(self):
        return {
            'ticks': len(self.frames),
            'class_distribution': dict(Counter(f.predicted_class for f in self.frames
                                               if f.predicted_class is not None)),
            'transitions': sum(f.transition is not None for f in self.frames),
            'initial_khz': self.metadata.get('initial_khz'),
            'final_khz': self.frames[-1].applied_khz if self.frames else None,
        }


def verify_archive(folder):
    """Check all archived hashes; permit only documented LF->CRLF text checkout.

    Byte-exact originals (CSV/PNG) are never normalized. Text normalization is
    accepted only when replacing CRLF with LF yields the manifest hash exactly.
    No Git executable, network or filesystem mutation is needed.
    """
    folder = Path(folder).resolve()
    try:
        entries = (folder / 'SHA256SUMS').read_text(encoding='utf-8').splitlines()
        checked = set()
        for line in entries:
            if not line.strip():
                continue
            expected, relative = line.split(None, 1)
            path = (folder / relative.lstrip('* ')).resolve()
            if not path.is_relative_to(folder) or path in checked:
                raise ValueError('invalid archive integrity manifest path')
            checked.add(path)
            data = path.read_bytes()
            exact = hashlib.sha256(data).hexdigest() == expected
            normalized = (path.suffix in {'.md', '.json', '.log'} and
                          hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest() == expected)
            if not exact and not normalized:
                raise ValueError(f'archive integrity mismatch: {path.name}')
        if not checked:
            raise ValueError('empty archive integrity manifest')
        return checked
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f'Cannot validate archive integrity at {folder}: {error}') from error


def load_csv(path, source_kind):
    """Read supported schema families, retaining extra fields for later consumers."""
    required = {'timestamp', 'util_pct', 'iowait_pct', 'ctxt_per_s',
                'procs_running', 'procs_blocked', 'freq_khz'}
    if source_kind == 'synthetic':
        required |= {'workload_class', 'target_khz', 'requested_khz', 'expected', 'est_power_w'}
    elif source_kind == 'linux_recorded':
        required |= {'elapsed_s', 'workload_label', 'observation_source',
                     'raw_prev_user', 'raw_cur_user'}
    else:
        raise ValueError('Unknown observation source/schema')
    with Path(path).open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if len(set(columns)) != len(columns) or not required.issubset(columns):
            raise ValueError(f'Unsupported {source_kind} CSV schema: {path}')
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('CSV row length does not match schema')
            for key in NUMERIC_FIELDS.intersection(row):
                if row[key] == '' and key == 'freq_khz':
                    row[key] = None
                    continue
                number = float(row[key])
                if not math.isfinite(number) or (key in INTEGER_FIELDS and not number.is_integer()):
                    raise ValueError(f'Invalid numeric CSV field: {key}')
                row[key] = int(number) if key in INTEGER_FIELDS else number
            if not 0 <= row['util_pct'] <= 100:
                raise ValueError('CPU utilization must be between 0 and 100')
            rows.append(row)
    if not rows:
        raise ValueError('Empty observation CSV')
    return rows


def policy_snapshot(policy, predicted_class):
    """Derived UI state, explicitly unavailable if backend introspection changes."""
    target = getattr(policy, '_target_freq', None)
    streak = getattr(policy, '_streak', None)
    pending = getattr(policy, '_pending', None)
    stable = getattr(policy, 'stable_class', None)
    candidate = target(predicted_class) if callable(target) else None
    known = isinstance(streak, int) and pending is not None and candidate is not None
    state = 'UNAVAILABLE'
    if known:
        state = 'STABLE' if stable == predicted_class else 'WAITING'
    return dict(candidate_khz=candidate, streak=streak, pending_class=pending,
                stable_class=stable, decision_state=state)


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _require_covered(checked, *paths):
    if any(Path(path).resolve() not in checked for path in paths):
        raise ValueError('Required input is not covered by archive integrity manifest')


def load_replay(folder=SYNTHETIC_ARCHIVE):
    """Reconstruct the archived scenario and verify every available output/input."""
    folder = Path(folder)
    checked = verify_archive(folder)
    csv_path, metadata_path = folder / 'ours.csv', folder / 'metadata.json'
    _require_covered(checked, csv_path, metadata_path)
    metadata = _json(metadata_path)
    if (metadata.get('inputs') != 'synthetic' or metadata.get('frequency_control') != 'simulated'
            or metadata.get('power_energy') != 'modelled'):
        raise ValueError('Archive source must be synthetic with simulated frequency and modelled power')
    try:
        plan, seed, k = metadata['plan'], metadata['seed'], metadata['k']
        freqs, interval = metadata['ladder_khz'], metadata['interval_s']
        if not isinstance(k, int) or k < 1 or not math.isfinite(interval) or interval <= 0:
            raise ValueError('invalid replay configuration')
        if not freqs or sorted(set(freqs)) != freqs or any(f <= 0 for f in freqs):
            raise ValueError('invalid frequency ladder')
        if not plan or any(not isinstance(ticks, int) or ticks < 1 for _, ticks in plan):
            raise ValueError('invalid scenario plan')
        # JSON stores lists; the existing synthetic API accepts (name, ticks) tuples.
        plan = [tuple(segment) for segment in plan]
    except (KeyError, TypeError) as error:
        raise ValueError('Required replay configuration missing or invalid') from error
    records = load_csv(csv_path, 'synthetic')
    if len(records) != sum(ticks for _, ticks in plan):
        raise ValueError('Replay length mismatch with archived plan')
    setter = SimulatedSetter(freqs)
    initial = setter.current
    policy = Policy(freqs, k=k)
    generated = run(source(plan, interval_s=interval, seed=seed), setter, policy)
    frames = []
    for tick, recorded in enumerate(records, 1):
        try:
            row = next(generated)
        except StopIteration as error:
            raise ValueError('Reconstructed replay length mismatch') from error
        for field in (*FEATURES[:-1], 'timestamp', 'util_pct', 'expected',
                      'workload_class', 'target_khz', 'requested_khz', 'est_power_w', 'freq_khz'):
            if field not in recorded:
                continue
            actual, expected = row.get(field), recorded[field]
            equal = (math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
                     if isinstance(expected, (int, float)) and isinstance(actual, (int, float))
                     else actual == expected)
            if not equal:
                raise ValueError(f'Backend/archive mismatch at tick {tick}: {field}')
        snapshot = policy_snapshot(policy, row['workload_class'])
        previous = frames[-1].applied_khz if frames else initial
        event = None
        if row['target_khz'] != previous:
            known = snapshot['decision_state'] != 'UNAVAILABLE'
            reason = (f"{snapshot['streak']} consecutive {row['workload_class']} samples; K={k} met"
                      if known else 'Recorded applied change; decision reason unavailable')
            event = Transition(tick, previous, row['target_khz'], row['workload_class'], reason)
            if known:
                snapshot['decision_state'] = 'APPLIED'
        frames.append(Frame(tick, f'{csv_path.as_posix()}:{tick + 1}', recorded['timestamp'],
                            recorded['util_pct'], {f: recorded[f] for f in FEATURES if f in recorded},
                            'synthetic', predicted_class=row['workload_class'],
                            applied_khz=row['target_khz'], transition=event, **snapshot))
    metadata = {**metadata, 'csv_path': str(csv_path.resolve()),
                'source_commit': metadata['commit'], 'initial_khz': initial,
                'validation': 'archive integrity and backend reconstruction passed',
                'derived_fields': 'candidate, pending/streak/stable state and transition reasons reconstructed with backend Policy',
                'limitations': 'Invented inputs; simulated frequency; provisional rules. Open-loop replay proves neither physical savings nor preserved completion time.'}
    return Dataset('SYNTHETIC REPLAY', tuple(frames), metadata)


def load_observations(folder=LINUX_ARCHIVE):
    """Display recorded Linux counters; never classify or simulate this capture."""
    folder = Path(folder)
    checked = verify_archive(folder)
    provenance_path, csv_path = folder / 'PROVENANCE.json', folder / 'validated_trace.csv'
    _require_covered(checked, provenance_path, csv_path)
    provenance = _json(provenance_path)
    records = load_csv(csv_path, 'linux_recorded')
    validate_trace(csv_path, expected_rows=5, label='uncontrolled_background', expected_jiffies_per_s=400)
    frames = tuple(Frame(tick, f'{csv_path.as_posix()}:{tick + 1}', row['timestamp'],
                         row['util_pct'], {f: row[f] for f in FEATURES if f in row}, 'linux_recorded')
                   for tick, row in enumerate(records, 1))
    return Dataset('RECORDED LINUX OBSERVATIONS', frames, {
        'csv_path': str(csv_path.resolve()), 'source_commit': provenance['source_commit'],
        'experiment_id': provenance['experiment_id'], 'observation_source': 'linux_proc_stat',
        'workload_label': 'uncontrolled_background',
        'validation': 'archive hashes and raw-counter validation passed',
        'limitations': 'Historical uncontrolled background capture; not live or idle ground truth. No frequency measurements. Does not establish loaded VM stability, classifier accuracy or energy savings.',
    })
