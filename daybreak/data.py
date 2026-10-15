"""Read-only dashboard views over the shared adapter and archived comparisons."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

import pandas as pd

from benchmark.baselines import BASELINES
from benchmark.compare import run_comparison
from benchmark import summarize as summary_engine
from monitor.synthetic import source
from presentation.adapter import SYNTHETIC_ARCHIVE, load_csv, load_replay, verify_archive


@dataclass(frozen=True)
class Comparison:
    policies: dict
    summaries: dict
    metadata: dict


def load_comparison(folder=SYNTHETIC_ARCHIVE):
    """Verify the five archived policies and summaries against existing backend."""
    folder = Path(folder)
    covered = verify_archive(folder)
    replay = load_replay(folder)
    metadata = replay.metadata
    names = (*BASELINES, 'ours')
    paths = [folder / f'{name}.csv' for name in names] + [folder / 'summaries.json']
    if any(path.resolve() not in covered for path in paths):
        raise ValueError('Comparison input missing from archive integrity manifest')
    plan = [tuple(item) for item in metadata['plan']]
    reconstructed = run_comparison(
        lambda: source(plan, interval_s=metadata['interval_s'], seed=metadata['seed']),
        metadata['ladder_khz'], k=metadata['k'])
    policies = {}
    summaries = json.loads((folder / 'summaries.json').read_text(encoding='utf-8'))
    if set(summaries) != set(names):
        raise ValueError('Archived summary policy names do not match implemented baselines')
    for name in names:
        rows = load_csv(folder / f'{name}.csv', 'synthetic')
        if len(rows) != len(reconstructed[name]):
            raise ValueError(f'Comparison length mismatch: {name}')
        for tick, (recorded, generated) in enumerate(zip(rows, reconstructed[name]), 1):
            for key, expected in recorded.items():
                actual = generated.get(key)
                same = (math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-9)
                        if isinstance(expected, (int, float)) and isinstance(actual, (int, float))
                        else expected == actual)
                if not same:
                    raise ValueError(f'Comparison backend mismatch: {name}, tick {tick}, {key}')
        calculated = summary_engine.summarize(rows, interval_s=metadata['interval_s'])
        if calculated != summaries[name]:
            raise ValueError(f'Archived summary mismatch: {name}')
        policies[name] = tuple(rows)
    return Comparison(policies, summaries, {**metadata, 'summary_validation': 'all five backend traces and archived summaries match'})


def move_tick(tick, delta, total):
    if total < 1:
        raise ValueError('Replay must contain at least one sample')
    return max(1, min(total, int(tick) + delta))


def inspect_decision(replay, tick):
    if not 1 <= tick <= len(replay.frames):
        raise ValueError('Selected tick is outside this replay')
    frame = replay.frames[tick - 1]
    k = replay.metadata['k']
    remaining = max(0, k - frame.streak) if frame.streak is not None else None
    return dict(tick=tick, predicted_class=frame.predicted_class,
                candidate_khz=frame.candidate_khz, applied_khz=frame.applied_khz,
                streak=frame.streak, remaining=remaining, state=frame.decision_state,
                transitions=sum(f.transition is not None for f in replay.frames[:tick]),
                k=k, sample_id=frame.sample_id)


def replay_table(replay):
    return pd.DataFrame([{'Tick': f.tick, 'CPU %': f.util_pct, 'Predicted workload': f.predicted_class,
                          'Candidate GHz (derived)': f.candidate_khz / 1e6 if f.candidate_khz is not None else None,
                          'Applied GHz (simulated)': f.applied_khz / 1e6 if f.applied_khz is not None else None,
                          'Streak (derived)': f.streak, **f.features} for f in replay.frames])


def observation_table(observations):
    return pd.DataFrame([{'Sample': f.tick, 'Original timestamp': f.timestamp, 'CPU %': f.util_pct,
                          'I/O wait %': f.features['iowait_pct'],
                          'Context switches/s': f.features['ctxt_per_s'],
                          'Elapsed seconds': f.features['elapsed_s'],
                          'Runnable': f.features['procs_running'], 'Blocked': f.features['procs_blocked']}
                         for f in observations.frames])


def comparison_table(comparison):
    return pd.DataFrame([{'Policy': name, 'Modelled energy (J)': values['total_energy_j'],
                          'Mean simulated GHz': values['mean_freq_khz'] / 1e6,
                          'Mean modelled power (W)': values['mean_power_w'],
                          'Simulated transitions': values['freq_change_count']}
                         for name, values in comparison.summaries.items()])
