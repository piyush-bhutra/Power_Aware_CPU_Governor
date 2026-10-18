"""benchmark.overhead with fake clock, sleep and /proc readers: nothing reads the real /proc."""
import ast
import csv
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
    """Clock advances only on sleep; governor ticks cost more CPU than control ticks."""
    ticks_per_s = 100

    def __init__(self, gov_tick_s=0.002, ctl_tick_s=0.0005, overshoot=0.0):
        self.now = self.cpu = 0.0
        self.counters = 0
        self.vol = self.inv = 0
        self.mode_cost = ctl_tick_s
        self.gov_tick_s, self.ctl_tick_s, self.overshoot = gov_tick_s, ctl_tick_s, overshoot
        self.stat_reads = 0

    def clock(self):
        return self.now

    def process_time(self):
        return self.cpu

    def sleep(self, seconds):
        self.now += seconds + self.overshoot
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
        ticks = round(self.cpu * self.ticks_per_s)
        return SELF_STAT.format(ut=ticks, st=0)

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


def test_governor_run_uses_real_pipeline_and_bounded_ticks():
    probe = FakeProbe()
    row = overhead.run_once(probe, 'governor', 0.5, 10)
    assert row['ticks'] == 20 and probe.stat_reads == 21  # baseline + one read per tick
    assert row['wall_s'] == pytest.approx(10)
    assert row['cpu_tick_mean_ms'] == pytest.approx(2.0)
    assert row['wakeups_per_s'] == pytest.approx(2.0)  # one voluntary switch per sleep
    assert row['rss_kib'] == 18000


def test_control_only_sleeps():
    probe = FakeProbe()
    row = overhead.run_once(probe, 'control', 1.0, 5)
    assert probe.stat_reads == 0 and row['cpu_tick_mean_ms'] == pytest.approx(0.5)


def test_net_is_governor_minus_control_and_projects_per_hour():
    probe = FakeProbe(gov_tick_s=0.002, ctl_tick_s=0.0005)
    plan = dict(intervals_s=(1.0, 2.0), duration_s=100.0, repetitions=2)
    rows = overhead.run_plan(probe, plan)
    assert [(r['repetition'], r['interval_s'], r['mode']) for r in rows][:4] == [
        (1, 1.0, 'governor'), (1, 1.0, 'control'), (1, 2.0, 'governor'), (1, 2.0, 'control')]
    assert rows[4]['mode'] == 'control'  # order alternates on repetition 2
    net = overhead.net_rows(rows)
    one_second = [n for n in net if n['interval_s'] == 1.0]
    assert len(one_second) == 2
    # 1.5 ms extra per 1 s tick = 0.15 % of one core = 5.4 CPU-s/hour
    assert one_second[0]['cpu_tick_mean_ms'] == pytest.approx(1.5)
    assert one_second[0]['cpu_pct_one_core'] == pytest.approx(0.15, abs=0.011)
    assert one_second[0]['cpu_s_per_hour'] == pytest.approx(5.4, abs=0.4)
    text = overhead.summary_markdown(rows, plan)
    assert '| 1 |' in text and '| 2 |' in text and 'not electrical power' in text


def test_unpaired_runs_are_rejected():
    probe = FakeProbe()
    row = {**overhead.run_once(probe, 'governor', 1.0, 2), 'repetition': 1}
    with pytest.raises(ValueError, match='unpaired'):
        overhead.net_rows([row])


def test_hard_timeout_stops_without_retry():
    probe = FakeProbe(overshoot=1.0)  # every sleep overruns by a second
    with pytest.raises(TimeoutError, match='hard limit'):
        overhead.run_once(probe, 'governor', 0.5, 10)


def test_fixed_plans_are_bounded():
    assert overhead.FULL_PLAN == dict(intervals_s=(0.5, 1.0, 2.0, 5.0), duration_s=60.0, repetitions=3)
    assert overhead.plan_budget_s(overhead.FULL_PLAN) == 1590
    assert overhead.plan_budget_s(overhead.SMOKE_PLAN) == 40


def test_main_writes_outputs_with_fake_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(overhead, 'FULL_PLAN', dict(intervals_s=(0.5, 1.0), duration_s=4.0, repetitions=2))
    out = io.StringIO()
    assert overhead.main(['--outdir', str(tmp_path / 'o')], probe_factory=FakeProbe, stream=out) == 0
    runs = list(csv.DictReader((tmp_path / 'o' / 'overhead_runs.csv').open()))
    assert len(runs) == 8 and set(runs[0]) == set(overhead.COLUMNS)
    assert len(list(csv.DictReader((tmp_path / 'o' / 'overhead_net.csv').open()))) == 4
    assert 'Governor self-overhead' in (tmp_path / 'o' / 'overhead_summary.md').read_text()


def test_refuses_non_linux_with_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(overhead.sys, 'platform', 'win32')
    out = io.StringIO()
    assert overhead.main(['--outdir', str(tmp_path / 'o')], stream=out) == 2
    assert 'refusing to run on win32' in out.getvalue()
    assert not (tmp_path / 'o').exists()


def test_refuses_non_empty_outdir(tmp_path):
    (tmp_path / 'keep.txt').write_text('x')
    with pytest.raises(SystemExit):
        overhead.main(['--outdir', str(tmp_path)], probe_factory=FakeProbe)


def test_no_other_module_imports_overhead():
    for path in ROOT.rglob('*.py'):
        if '.venv' in path.parts or path.name in ('overhead.py', 'test_overhead.py'):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [f'{node.module}.{a.name}' for a in node.names] if isinstance(node, ast.ImportFrom) else [])
            assert not any('overhead' in name for name in names), path
