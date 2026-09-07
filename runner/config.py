"""Read benchmark credentials as data, never as shell code."""
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str = field(repr=False)
    model_id: str = ''


def load_config(path=Path('.env')):
    values = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key.strip().startswith('QWEN_'):
            raise ValueError(f'Invalid config line {number}')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    for key in ('QWEN_BASE_URL', 'QWEN_API_KEY'):
        if not values.get(key):
            raise ValueError(f'Missing {key}')
    url = urlsplit(values['QWEN_BASE_URL'])
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Invalid QWEN_BASE_URL: expected HTTP(S) API root without credentials, query or fragment')
    return Config(values['QWEN_BASE_URL'].rstrip('/'), values['QWEN_API_KEY'], values.get('QWEN_MODEL_ID', ''))
