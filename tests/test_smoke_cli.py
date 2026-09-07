import subprocess
import sys
import unittest

class SmokeCliTests(unittest.TestCase):
    def test_help_accepts_separate_env_without_api_request(self):
        result = subprocess.run([sys.executable, '-m', 'runner.smoke', '--help'], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--env', result.stdout)

if __name__ == '__main__':
    unittest.main()
