import tempfile
import time
import unittest
from pathlib import Path
from runner.state import atomic_json
from runner.observer import snapshot

class ObserverTests(unittest.TestCase):
    def test_guard_death_visible_even_when_runner_claims_running(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run-1'; p.mkdir()
            atomic_json(p/'guard.json', {'heartbeat':time.time()-30, 'status':'watching'})
            atomic_json(p/'runner.json', {'heartbeat':time.time(), 'phase':'generating'})
            item=snapshot(Path(d))['runs'][0]
            self.assertEqual(item['health'], 'guard_stale')

    def test_dashboard_script_parses(self):
        import subprocess
        from runner.observer import HTML
        script=HTML.split('<script>')[1].split('</script>')[0]
        r=subprocess.run(['node','--check','--input-type=commonjs'],input=script,text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
