import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GuardTests(unittest.TestCase):
    def test_stopped_runner_is_killed_and_reported(self):
        with tempfile.TemporaryDirectory() as d:
            result = subprocess.run([sys.executable, '-m', 'runner.guard', '--run-dir', d,
                '--stale-seconds', '0.4', '--deadline-seconds', '3', '--',
                sys.executable, '-c', 'import os,signal; os.kill(os.getpid(),signal.SIGSTOP)'], cwd=ROOT, timeout=6)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((Path(d)/'guard.json').read_text())
            self.assertEqual(state['reason'], 'runner_heartbeat_stale')
            self.assertEqual(state['status'], 'terminated')

if __name__ == '__main__': unittest.main()

class DeadlineTests(unittest.TestCase):
    def test_active_heartbeats_do_not_disable_hard_deadline(self):
        with tempfile.TemporaryDirectory() as d:
            code="import os,time; from runner.state import heartbeat; p=os.environ['SHELLSEM_RUN_DIR']; exec('while True:\\n heartbeat(p,\"busy\")\\n time.sleep(.03)')"
            result=subprocess.run([sys.executable,'-m','runner.guard','--run-dir',d,'--stale-seconds','2','--deadline-seconds','.4','--',sys.executable,'-c',code],cwd=ROOT,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(json.loads((Path(d)/'guard.json').read_text())['reason'],'hard_deadline')
