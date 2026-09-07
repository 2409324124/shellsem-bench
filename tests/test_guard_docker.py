import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from runner.state import read_json

@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','explicit Docker integration test')
class GuardDockerTests(unittest.TestCase):
    def test_hung_runner_container_is_removed_by_external_guard(self):
        with tempfile.TemporaryDirectory() as d:
            code="import os,signal; from runner.sandbox import Sandbox; from runner.state import heartbeat; p=os.environ['SHELLSEM_RUN_DIR']; s=Sandbox(p).start(); heartbeat(p,'frozen'); os.kill(os.getpid(),signal.SIGSTOP)"
            result=subprocess.run([sys.executable,'-m','runner.guard','--run-dir',d,'--stale-seconds','2','--deadline-seconds','8','--',sys.executable,'-c',code],timeout=15)
            self.assertNotEqual(result.returncode,0)
            state=read_json(Path(d)/'guard.json')
            self.assertEqual(state['reason'],'runner_heartbeat_stale')
            self.assertEqual(state['cleanup_errors'],[])
            names=read_json(Path(d)/'containers.json')['names']
            self.assertEqual(len(names),1)
            self.assertNotEqual(subprocess.run(['docker','inspect',names[0]],capture_output=True).returncode,0)
