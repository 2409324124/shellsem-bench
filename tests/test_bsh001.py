import os
from pathlib import Path
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','explicit Docker integration test')
class BSH001Tests(unittest.TestCase):
    def test_reference_passes_and_empty_answer_fails(self):
        from verifier.evaluate import evaluate
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            rows=evaluate('BSH001',Path('reference/BSH001.sh').read_bytes(),p)
            self.assertEqual(len(rows),6)
            self.assertTrue(all(r['passed'] for r in rows),rows)
            rows=evaluate('BSH001',b'#!/bin/bash\nexit 0\n',p)
            self.assertFalse(all(r['passed'] for r in rows))
