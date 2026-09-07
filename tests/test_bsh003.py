import os
from pathlib import Path
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','explicit Docker integration test')
class BSH003Tests(unittest.TestCase):
    def test_partial_producer_failure_is_not_success(self):
        from verifier.evaluate import evaluate
        with tempfile.TemporaryDirectory() as d:
            rows=evaluate('BSH003',Path('reference/BSH003.sh').read_bytes(),Path(d))
            self.assertEqual(len(rows),6)
            self.assertTrue(all(r['passed'] for r in rows),rows)
