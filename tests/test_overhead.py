"""benchmark.overhead with fake clock, sleep and /proc readers: nothing reads the real /proc."""
import ast
import csv
from datetime import datetime, timezone
import io
from pathlib import Path

import pytest

from benchmark import overhead

ROOT = Path(__file__).resolve().parents[1]
STAT = ('cpu  {u} 0 {s} {i} 0 0 0 0 0 0\nctxt {c}\nprocs_running 1\nprocs_blocked 0\n')
SELF_STAT = '4242 (python3 -m x) S 1 2 3 4 5 6 7 8 9 10 {ut} {st} 0 0 20 0 1 0 100 1000 200'
SELF_STATUS = ('Name:\tpython3\nVmHWM:\t{hwm} kB\nVmRSS:\t{rss} kB\n'
               'voluntary_ctxt_switches:\t{vol}\nnonvoluntary_ctxt_switches:\t{inv}\n')


class FakeProbe:
    """Clock advances only on sleep (times 1 + overshoot); governor ticks cost more CPU than control."""
    ticks_per_s = 100

    def __init__(self, gov_tick_s=0.002, ctl_tick_s=0.0005, overshoot=0.0, fail_on=None):
        self.now = self.cpu = 0.0
        self.counters = 0
        self.vol = self.inv = 0
        self.gov_tick_s, self.ctl_tick_s, self.overshoot = gov_tick_s, ctl_tick_s, overshoot
        self.fail_on = fail_on  # (call number of self_stat) that raises
        self.stat_reads = self.self_stat_calls = 0

    def clock(self):
        return self.now

    def process_time(self):
        return self.cpu

    def sleep(self, seconds):
        self.now += seconds * (1 + self.overshoot)
        self.cpu += self.ctl_tick_s
        self.vol += 1

    def read_stat(self):
        self.stat_reads += 1
        self.cpu += self.gov_tick_s - self.ctl_tick_s
        self.inv += 1
        self.counters += 100
        return STAT.format(u=self.counters // 2, s=self.counters // 10, i=self.counters, c=self.counters * 3)

    def read_freq(self):
        return None

    def self_stat(self):
        self.self_stat_calls += 1
        if self.self_stat_calls == self.fail_on:
            raise OSError('fixture /proc/self/stat read failed')
        return SELF_STAT.format(ut=round(self.cpu * self.ticks_per_s), st=0)

    def self_status(self):
        return SELF_STATUS.format(hwm=20000, rss=18000, vol=self.vol, inv=self.inv)


def test_parsers_handle_spaces_in_comm_and_required_status_fields():
    assert overhead.parse_self_stat(SELF_STAT.format(ut=250, st=50), 100) == 3.0
    parsed = overhead.parse_self_status(SELF_STATUS.format(hwm=5, rss=4, vol=7, inv=2))
    assert parsed == {'hwm_kib': 5, 'rss_kib': 4, 'voluntary': 7, 'involuntary': 2}
    with pytest.raises(ValueError, match='lacks'):
        overhead.parse_self_status('VmRSS:\t1 kB\n')


def test_percentile_nearest_rank():
    assert overhead.percentile(list(range(1, 101)), 95) == 95
    assert overhead.percentile([3.0], 95) == 3.0


def test_governor_run_uses_real_pipeline_and_fixed_tick_count():
    probe = FakeProbe()
    row = overhead.run_once(probe, 'governor', 0.5, 10)
    assert row['ticks'] == row['planned_ticks'] == 20 and probe.stat_reads == 21  # baseline + one per tick
    assert row['actual_elapsed_s'] == pytest.approx(10) and row['overshoot_ratio'] == pytest.approx(1)
    assert row['cpu_tick_mean_ms'] == pytest.approx(2.0)
    assert row['wakeups_per_s'] == pytest.approx(2.0)  # one voluntary switch per sleep
    assert row['rss_kib'] == 18000 and row['status'] == 'ok'


def test_control_only_sleeps():
    probe = FakeProbe()
    row = overhead.run_once(probe, 'control', 1.0, 5)
    assert probe.stat_reads == 0 and row['cpu_tick_mean_ms'] == pytest.approx(0.5)


def test_overshooting_run_completes_and_records_the_ratio():
    probe = FakeProbe(overshoot=0.12)  # 12 % sleep overshoot, as seen on the VM
    row = overhead.run_once(probe, 'control', 0.5, 60)
    assert row['status'] == 'ok' and row['ticks'] == 120
    assert row['actual_elapsed_s'] == pytest.approx(67.2)  # would have broken the old 65 s limit
    assert row['overshoot_ratio'] == pytest.approx(1.12)
    assert row['sleep_overshoot_mean_ms'] == pytest.approx(60.0)
    assert row['sleep_overshoot_p95_ms'] == pytest.approx(60.0) and row['sleep_overshoot_max_ms'] == pytest.approx(60.0)


def test_derived_cpu_percent_and_hourly_projection():
    row = overhead.run_once(FakeProbe(gov_tick_s=0.003, ctl_tick_s=0.003), 'governor', 2.0, 20)
    # 3 ms per 2 s tick = 0.15 % of one core = 5.4 CPU-s per hour
    assert row['cpu_pct_one_core_derived'] == pytest.approx(0.15)
    assert row['cpu_s_per_hour_derived'] == pytest.approx(5.4)


def test_runaway_guard_still_stops_a_run():
    probe = FakeProbe(overshoot=2.5)  # each 1 s sleep takes 3.5 s: past 3x planned
    with pytest.raises(overhead.RunawayGuard, match='runaway guard'):
        overhead.run_once(probe, 'governor', 1.0, 10)
    assert probe.now < 3 * 10 + 3.5 * 2  # stopped soon after crossing 30 s


def test_failed_run_is_recorded_and_plan_continues():
    probe = FakeProbe(fail_on=3)  # second run's first /proc/self/stat read fails
    plan = dict(intervals_s=(1.0,), duration_s=4.0, repetitions=2)
    seen = []
    rows = overhead.run_plan(probe, plan, on_row=lambda partial: seen.append(len(partial)))
    assert [(r['repetition'], r['mode'], r['status']) for r in rows] == [
        (1, 'governor', 'ok'), (1, 'control', 'failed'), (2, 'control', 'ok'), (2, 'governor', 'ok')]
    assert rows[1]['failure_reason'] == 'OSError: fixture /proc/self/stat read failed'
    assert seen == [1, 2, 3, 4]  # partial outputs after every run
    assert [n['repetition'] for n in overhead.net_rows(rows)] == [2]  # unpaired rep 1 excluded


def test_net_is_governor_minus_control():
    probe = FakeProbe(gov_tick_s=0.002, ctl_tick_s=0.0005)
    plan = dict(intervals_s=(1.0, 2.0), duration_s=100.0, repetitions=2)
    rows = overhead.run_plan(probe, plan)
    assert rows[4]['mode'] == 'control'  # order alternates on repetition 2
    one_second = [n for n in overhead.net_rows(rows) if n['interval_s'] == 1.0]
    assert len(one_second) == 2
    assert one_second[0]['cpu_tick_mean_ms'] == pytest.approx(1.5)
    assert one_second[0]['cpu_pct_one_core_derived'] == pytest.approx(0.15)
    assert one_second[0]['cpu_s_per_hour_derived'] == pytest.approx(5.4)
    text = overhead.summary_markdown(rows, plan)
    assert '## VM timer overshoot' in text and '(derived)' in text and 'quantized to the 10 ms' in text


def test_plan_budgets():
    assert overhead.FULL_PLAN == dict(intervals_s=(0.5, 1.0, 2.0, 5.0), duration_s=60.0, repetitions=3)
    assert overhead.plan_nominal_s(overhead.FULL_PLAN) == 1440
    assert overhead.plan_budget_s(overhead.FULL_PLAN) == 4320
    assert overhead.plan_nominal_s(overhead.SMOKE_PLAN) == 20
    assert overhead.plan_nominal_s(dict(intervals_s=overhead.INTERVALS_S, duration_s=30, repetitions=2)) == 480


def run_main(tmp_path, monkeypatch, *argv, probe=FakeProbe):
    monkeypatch.setattr(overhead, 'ROOT', tmp_path)
    out = io.StringIO()
    now = datetime(2026, 10, 19, 8, 30, 5, tzinfo=timezone.utc)
    return overhead.main(list(argv), probe_factory=probe, stream=out, now=now), out.getvalue()


def test_default_outdir_naming(tmp_path, monkeypatch):
    monkeypatch.setattr(overhead, 'SMOKE_PLAN', dict(intervals_s=(1.0,), duration_s=2.0, repetitions=1))
    code, out = run_main(tmp_path, monkeypatch, '--smoke')
    assert code == 0 and (tmp_path / 'data' / 'overhead-smoke-20261019T083005Z' / 'overhead_summary.md').exists()
    monkeypatch.setattr(overhead, 'FULL_PLAN', dict(intervals_s=(1.0,), duration_s=2.0, repetitions=1))
    code, out = run_main(tmp_path, monkeypatch)
    assert code == 0 and (tmp_path / 'data' / 'overhead-20261019T083005Z' / 'overhead_runs.csv').exists()


def test_duration_and_repetition_flags(tmp_path, monkeypatch):
    code, out = run_main(tmp_path, monkeypatch, '--duration-s', '4', '--repetitions', '2', '--outdir', str(tmp_path / 'o'))
    assert code == 0 and "'duration_s': 4.0" in out and "'repetitions': 2" in out
    runs = overhead.read_runs(tmp_path / 'o' / 'overhead_runs.csv')
    assert len(runs) == 16 and {r['planned_s'] for r in runs if r['interval_s'] == 0.5} == {4.0}
    for bad in (['--duration-s', '0.5'], ['--duration-s', '301'], ['--repetitions', '6'], ['--repetitions', '0']):
        with pytest.raises(SystemExit):
            run_main(tmp_path, monkeypatch, *bad)


def test_failures_write_partial_files_and_exit_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(overhead, 'FULL_PLAN', dict(intervals_s=(1.0,), duration_s=3.0, repetitions=1))
    code, out = run_main(tmp_path, monkeypatch, '--outdir', str(tmp_path / 'o'), probe=lambda: FakeProbe(fail_on=1))
    assert code == 1 and '1 runs ok, 1 failed' in out
    runs = overhead.read_runs(tmp_path / 'o' / 'overhead_runs.csv')
    assert [r['status'] for r in runs] == ['failed', 'ok']
    assert 'Failed runs (recorded, not retried)' in (tmp_path / 'o' / 'overhead_summary.md').read_text()


def test_old_csv_columns_still_parse(tmp_path):
    assert set(overhead.LEGACY_COLUMNS) <= set(overhead.COLUMNS)
    old = tmp_path / 'old.csv'
    with old.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, overhead.LEGACY_COLUMNS)
        writer.writeheader()
        writer.writerow({c: ('governor' if c == 'mode' else 1) for c in overhead.LEGACY_COLUMNS})
    (row,) = overhead.read_runs(old)
    assert row['status'] == 'ok' and row['cpu_pct_one_core'] == 1.0 and 'overshoot_ratio' not in row


def test_refuses_non_linux_with_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(overhead.sys, 'platform', 'win32')
    code, out = run_main(tmp_path, monkeypatch, '--outdir', str(tmp_path / 'o'), probe=overhead.LinuxProbe)
    assert code == 2 and 'refusing to run on win32' in out
    assert not (tmp_path / 'o').exists()


def test_refuses_non_empty_outdir(tmp_path, monkeypatch):
    (tmp_path / 'keep.txt').write_text('x')
    with pytest.raises(SystemExit):
        run_main(tmp_path, monkeypatch, '--outdir', str(tmp_path))


def test_no_other_module_imports_overhead():
    for path in ROOT.rglob('*.py'):
        if '.venv' in path.parts or path.name in ('overhead.py', 'test_overhead.py'):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [f'{node.module}.{a.name}' for a in node.names] if isinstance(node, ast.ImportFrom) else [])
            assert not any('overhead' in name for name in names), path
