import tempfile
import unittest
from pathlib import Path
from runner.config import load_config

class ConfigTests(unittest.TestCase):
    def test_missing_endpoint_rejected_without_exposing_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '.env'
            p.write_text('QWEN_API_KEY=secret-test-value\nQWEN_BASE_URL=\n')
            with self.assertRaises(ValueError) as caught:
                load_config(p)
            self.assertIn('QWEN_BASE_URL', str(caught.exception))
            self.assertNotIn('secret-test-value', str(caught.exception))

class LiteralConfigTests(unittest.TestCase):
    def test_shell_text_is_literal_and_key_is_not_in_repr(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '.env'
            marker = Path(d) / 'executed'
            secret = f'$(touch {marker})'
            p.write_text(f'QWEN_BASE_URL=https://example.invalid/v1/\nQWEN_API_KEY={secret}\n')
            config = load_config(p)
            self.assertEqual(config.api_key, secret)
            self.assertFalse(marker.exists())
            self.assertNotIn(secret, repr(config))
            self.assertEqual(config.base_url, 'https://example.invalid/v1')

if __name__ == '__main__':
    unittest.main()
