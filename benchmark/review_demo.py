"""Export a finite, deterministic Review 1 demo; no hardware access or stress."""
import argparse
import json
from pathlib import Path
import subprocess

from analysis.plots import plot_energy_comparison, plot_frequency_timeline
from benchmark.compare import run_comparison
from benchmark.summarize import compare_table
from governor import EXTRA_COLS
from hardware_profile import RYZEN_7840HS_LADDER_KHZ
from monitor.reader import log_csv
from monitor.synthetic import source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', required=True,
                        help='new local output directory (existing files are refused)')
    args = parser.parse_args()
    output = Path(args.outdir)
    names = ['metadata.json', 'summaries.json', 'synthetic_modelled_energy.png',
             'synthetic_simulated_frequency.png']
    names += [f'{name}.csv' for name in
              ('ours', 'performance', 'powersave', 'ondemand', 'conservative')]
    if any((output / name).exists() for name in names):
        parser.error('output artifacts already exist; choose a new --outdir')
    output.mkdir(parents=True, exist_ok=True)

    plan = [('cpu', 10), ('io_burst', 10), ('idle', 6), ('mixed', 8)]
    results = run_comparison(lambda: source(plan, seed=11), RYZEN_7840HS_LADDER_KHZ)
    print('SYNTHETIC inputs | SIMULATED frequency | MODELLED energy | interval=1s, seed=11')
    summaries = compare_table(results)
    for name, rows in results.items():
        log_csv(output / f'{name}.csv', rows, EXTRA_COLS)
    (output / 'summaries.json').write_text(json.dumps(summaries, indent=2) + '\n')
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, timeout=5)
    dirty = subprocess.run(['git', 'status', '--porcelain'], capture_output=True,
                           text=True, timeout=5)
    metadata = dict(inputs='synthetic', frequency_control='simulated',
                    power_energy='modelled', interval_s=1.0, seed=11, k=3,
                    plan=plan, ladder_khz=RYZEN_7840HS_LADDER_KHZ,
                    commit=revision.stdout.strip() or 'unavailable',
                    working_tree_dirty=bool(dirty.stdout.strip()),
                    limitations='Open-loop policy approximations; no measured energy or completion-time evidence.')
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    plot_energy_comparison(summaries, output / 'synthetic_modelled_energy.png',
                          title='SYNTHETIC replay: modelled energy (simulated frequency)')
    plot_frequency_timeline(results, output / 'synthetic_simulated_frequency.png',
                            title='SYNTHETIC replay: SIMULATED frequency decisions')
    print(f'Evidence saved to {output}')


if __name__ == '__main__':
    main()
