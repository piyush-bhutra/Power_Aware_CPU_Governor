"""Fixed five-interval background-only launcher; never selects a stressor profile."""
from pathlib import Path
import sys

from benchmark.safe_cpu_launcher import run_launcher


def main():
    if len(sys.argv)!=1:
        print('No command-line overrides are accepted; run without arguments.',file=sys.stderr)
        return 2
    return run_launcher(Path(__file__).resolve().parents[1],Path('/media/sf_OS_Project_Shared'),
                        profile='background')


if __name__=='__main__':
    raise SystemExit(main())
