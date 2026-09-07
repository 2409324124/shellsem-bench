"""A process outside the runner. Detects SIGSTOP, crashes and hard deadlines."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import time
from runner.state import atomic_json, read_json


def cleanup_containers(run_dir):
    # The runner registers names before creation. Never prune unrelated containers.
    errors = []
    for name in read_json(run_dir/'containers.json').get('names', []):
        if not isinstance(name, str) or not name.startswith('shellsem-'):
            errors.append('invalid_container_name')
            continue
        try:
            r = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=8)
            if r.returncode and b'No such container' not in r.stderr:
                errors.append(name)
        except (OSError, subprocess.TimeoutExpired):
            errors.append(name)
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--stale-seconds', type=float, default=15)
    parser.add_argument('--deadline-seconds', type=float, default=900)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    env = os.environ.copy()
    env['SHELLSEM_RUN_DIR'] = str(args.run_dir.resolve())
    start = time.monotonic()
    started_at = time.time()
    interrupted = []
    signal.signal(signal.SIGTERM, lambda *_: interrupted.append('guard_signal'))
    signal.signal(signal.SIGINT, lambda *_: interrupted.append('guard_signal'))
    with (args.run_dir/'runner.log').open('ab', buffering=0) as log:
        child = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        reason = None
        while child.poll() is None:
            now = time.time()
            state = read_json(args.run_dir/'runner.json')
            beat = state.get('heartbeat', started_at)
            atomic_json(args.run_dir/'guard.json', {'pid': os.getpid(), 'runner_pid': child.pid,
                'heartbeat': now, 'status': 'watching', 'runner_heartbeat_age': max(0, now-beat),
                'elapsed': time.monotonic()-start})
            if interrupted: reason = interrupted[0]
            elif now-beat > args.stale_seconds: reason = 'runner_heartbeat_stale'
            elif time.monotonic()-start > args.deadline_seconds: reason = 'hard_deadline'
            if reason:
                break
            time.sleep(0.1)
        # Kill the whole session even after a normal runner exit: reap escaped host children.
        try: os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        child.wait(timeout=3)
    errors = cleanup_containers(args.run_dir)
    atomic_json(args.run_dir/'guard.json', {'pid': os.getpid(), 'runner_pid': child.pid,
        'heartbeat': time.time(), 'status': 'terminated' if reason else 'finished',
        'reason': reason or ('runner_completed' if child.returncode == 0 else 'runner_failed'),
        'returncode': child.returncode, 'elapsed': time.monotonic()-start, 'cleanup_errors': errors})
    return 1 if reason or child.returncode or errors else 0

if __name__ == '__main__': raise SystemExit(main())
