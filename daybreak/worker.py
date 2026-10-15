"""Single-purpose Linux child. Collection runs only in this module's main()."""
import argparse
import json
from pathlib import Path
import signal


def write_status(job, value):
    temporary = job / 'status.tmp'
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(job / 'status.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    args = parser.parse_args(argv)
    job = args.job.resolve()
    # Imported only on explicit child invocation. No duplicated sampling/policy code.
    from governorlab.live import collect_live
    from daybreak.sessions import session_hashes
    try:
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
        data = collect_live(job, lambda count: write_status(job, {'status': 'collecting', 'count': count}))
        folder = Path(data.metadata['csv_path']).parent
        (folder / 'session-sha256.json').write_text(json.dumps(session_hashes(folder)), encoding='utf-8')
        write_status(job, {'status': 'validated', 'count': len(data.frames), 'folder': folder.name})
        return 0
    except BaseException as error:
        write_status(job, {'status': 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed',
                           'error': f'{type(error).__name__}: {error}',
                           'evidence': getattr(error, 'live_evidence', None)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
