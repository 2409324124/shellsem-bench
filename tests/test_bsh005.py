import os
from pathlib import Path
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','explicit Docker integration test')
class BSH005Tests(unittest.TestCase):
    def test_signal_descendants_and_publication(self):
        from verifier.evaluate import evaluate
        with tempfile.TemporaryDirectory() as d:
            rows=evaluate('BSH005',Path('reference/BSH005.sh').read_bytes(),Path(d))
            self.assertEqual(len(rows),6)
            self.assertTrue(all(r['passed'] for r in rows),rows)
