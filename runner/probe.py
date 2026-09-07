"""Read-only model discovery. Never follow redirects carrying credentials."""
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from runner.config import load_config

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', type=Path, default=Path('.env'))
    args = parser.parse_args()
    try:
        config = load_config(args.env)
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'configuration_error', 'message': str(exc)}))
        return 2
    request = urllib.request.Request(config.base_url + '/models', headers={'Authorization': 'Bearer ' + config.api_key})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            data = json.load(response)
            print(json.dumps({'status': response.status, 'models': [m.get('id') for m in data.get('data', [])]}, ensure_ascii=False))
            return 0
    except urllib.error.HTTPError as exc:
        print(json.dumps({'status': 'http_error', 'http_status': exc.code}))
    except Exception as exc:
        print(json.dumps({'status': 'transport_or_response_error', 'error_type': type(exc).__name__}))
    return 1

if __name__ == '__main__':
    raise SystemExit(main())
