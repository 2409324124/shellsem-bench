import os
from pathlib import Path
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','explicit Docker integration test')
class MutationTests(unittest.TestCase):
    def test_each_semantic_verifier_rejects_a_known_wrong_solution(self):
        from verifier.evaluate import evaluate
        mutations=[
            ('BSH002','source_failure',lambda s:s.replace('status=("${PIPESTATUS[@]}")','echo overwritten >/dev/null; status=("${PIPESTATUS[@]}")')),
            ('BSH003','partial_failure',lambda s:s.replace('else rc=$?; exit "$rc"; fi','else :; fi')),
            ('BSH004','ordered',lambda s:s.replace('start+=4','start+=1').replace('end=$((start+4))','end=$((start+1))')),
            ('BSH005','sigterm_tree',lambda s:s.replace('"-$p"','"$p"').replace('"-${pids[i]}"','"${pids[i]}"')),
        ]
        for task,case,mutate in mutations:
            with self.subTest(task=task),tempfile.TemporaryDirectory() as d:
                original=Path(f'reference/{task}.sh').read_text();bad=mutate(original)
                self.assertNotEqual(original,bad)
                rows=evaluate(task,bad.encode(),Path(d),only_cases=[case])
                self.assertEqual(len(rows),1)
                self.assertFalse(rows[0]['passed'],rows)
