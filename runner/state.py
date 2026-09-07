"""Independent, atomic state files. No credentials belong in telemetry."""
import json
import os
from pathlib import Path
import time


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False))
    tmp.replace(path)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def heartbeat(run_dir, phase, **extra):
    atomic_json(Path(run_dir)/'runner.json', {'pid': os.getpid(), 'heartbeat': time.time(), 'phase': phase, **extra})
