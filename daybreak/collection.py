"""Explicit child ownership with finite watchdog, heartbeat lease and reaping."""
import atexit
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import weakref

ROOT = Path(__file__).resolve().parents[1]
JOBS = weakref.WeakSet()


class Collection:
    def __init__(self, child, folder):
        self.child, self.folder = child, Path(folder)
        self.started = self.heartbeat = time.monotonic()
        self.result = None
        self.lock = threading.RLock()
        JOBS.add(self)

    @classmethod
    def start(cls, root=ROOT / 'run', current=None):
        if current is not None and current.child.poll() is None:
            raise RuntimeError('A collection is already active in this user session')
        if sys.platform != 'linux':
            raise RuntimeError('Collect Live Data requires Linux /proc/stat; saved replay works on Windows')
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix='daybreak-', dir=root))
        child = subprocess.Popen([sys.executable, '-m', 'daybreak.worker', '--job', str(folder.resolve())],
                                 cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        job = cls(child, folder)
        threading.Thread(target=job._watch, daemon=True, name='daybreak-bounded-collection').start()
        return job

    @property
    def active(self):
        return self.child.poll() is None

    def _watch(self):
        # No Streamlit calls from background threads. Deadline is independent of UI.
        while self.active:
            now = time.monotonic()
            if now - self.started >= 15:
                self.cancel('timeout')
                return
            if now - self.heartbeat >= 6:
                self.cancel('disconnected')
                return
            time.sleep(.1)
        self.child.wait(timeout=.5)

    def cancel(self, reason='cancelled'):
        with self.lock:
            if self.result is not None:
                return
            if self.active:
                try:
                    os.killpg(self.child.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    self.child.wait(timeout=.3)
                except subprocess.TimeoutExpired:
                    self.child.kill()  # child pipeline never launches descendants
                    self.child.wait(timeout=.5)
            self.result = {'status': reason, 'error': f'Collection {reason}; no automatic retry. Artifacts retained at {self.folder}'}

    def poll(self):
        with self.lock:
            self.heartbeat = time.monotonic()
            if self.result is not None:
                return self.result
            try:
                result = json.loads((self.folder / 'status.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                result = {'status': 'collecting', 'count': 0}
            if self.active:
                return {'status': 'collecting', 'count': result.get('count', 0)}
            code = self.child.wait(timeout=.5)
            if code != 0 or result.get('status') != 'validated':
                result = {'status': 'failed', 'error': result.get('error', f'Child exited ({code}) without a validated session'),
                          'evidence': result.get('evidence', str(self.folder))}
            self.result = result
            return result


def cleanup():
    for job in list(JOBS):
        job.cancel('server stopped')


atexit.register(cleanup)
