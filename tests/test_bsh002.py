import os
from pathlib import Path
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','explicit Docker integration test')
class BSH002Tests(unittest.TestCase):
    def test_reference_preserves_real_pipeline_codes(self):
        from verifier.evaluate import evaluate
        with tempfile.TemporaryDirectory() as d:
            rows=evaluate('BSH002',Path('reference/BSH002.sh').read_bytes(),Path(d))
            self.assertEqual(len(rows),6)
            self.assertTrue(all(r['passed'] for r in rows),rows)
