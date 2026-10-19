"""Archived Phase 1B overhead run (Ubuntu VM): integrity and internal consistency."""
import csv
import json
import math
from pathlib import Path

from benchmark import overhead
from presentation.adapter import verify_archive

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence' / 'phase1b_overhead'
FILES = {'overhead_runs.csv', 'overhead_net.csv', 'overhead_summary.md', 'PROVENANCE.json'}


def runs():
    rows = overhead.read_runs(EVIDENCE / 'overhead_runs.csv')
    for row in rows:
        row['repetition'] = int(row['repetition'])
    return rows


def test_overhead_evidence_verifies():
    assert {p.name for p in verify_archive(EVIDENCE)} == FILES
    provenance = json.loads((EVIDENCE / 'PROVENANCE.json').read_text(encoding='utf-8'))
    assert provenance['source_commit'].startswith('f47e288')
    assert {f['path'] for f in provenance['archived_files']} == FILES - {'PROVENANCE.json'}


def test_overhead_runs_are_complete_and_ok():
    rows = runs()
    assert len(rows) == 24 and all(r['status'] == 'ok' for r in rows)
    assert {(r['interval_s'], r['mode'], r['repetition']) for r in rows} == {
        (i, m, rep) for i in overhead.INTERVALS_S for m in overhead.MODES for rep in (1, 2, 3)}


def test_net_table_matches_runs():
    expected = overhead.net_rows(runs())
    with (EVIDENCE / 'overhead_net.csv').open(newline='', encoding='utf-8') as handle:
        archived = list(csv.DictReader(handle))
    assert len(archived) == len(expected) == 12
    for row, want in zip(archived, expected):
        for key, value in want.items():
            assert math.isclose(float(row[key]), value, rel_tol=1e-9, abs_tol=1e-9), key


def test_summary_reports_all_runs_ok():
    text = (EVIDENCE / 'overhead_summary.md').read_text(encoding='utf-8')
    assert 'Runs: 24 ok, 0 failed.' in text and '## VM timer overshoot' in text


def test_summary_regenerates_from_runs():
    regenerated = overhead.summary_markdown(runs(), overhead.FULL_PLAN)
    assert (EVIDENCE / 'overhead_summary.md').read_bytes() == regenerated.encode('utf-8')
