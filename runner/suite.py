"""Resume a one-run-per-model smoke matrix, with at most two guarded runs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from runner.state import read_json,atomic_json

ROOT=Path(__file__).resolve().parents[1]


def guard_alive(state):
    pid=state.get('pid')
    if not pid:return False
    try:
        cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
        return b'runner.guard' in cmd
    except OSError:return False


def main():
    root=ROOT/'runs'
    jobs=[(label,task) for task in [f'BSH00{i}' for i in range(1,6)] for label in ('baseline','preview')]
    children=[]
    while True:
        active=[];pending=[];finished=[];orphaned=[]
        for label,task in jobs:
            p=root/f'smoke-low-{label}-{task}'
            guard=read_json(p/'guard.json')
            if guard.get('status') in ('finished','terminated'):finished.append(p.name)
            elif guard.get('status')=='watching':
                if guard_alive(guard):active.append(p.name)
                else:orphaned.append(p.name)
            elif p.exists():orphaned.append(p.name)
            else:pending.append((label,task,p))
        for label,task,p in pending[:max(0,2-len(active))]:
            p.mkdir()
            with (root/'launch.log').open('ab') as log:
                child=subprocess.Popen([sys.executable,'-m','runner.guard','--run-dir',str(p),'--deadline-seconds','600','--',sys.executable,'-m','runner.execute','--task',task,'--label',label],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
                children.append(child)
            active.append(p.name)
        atomic_json(root/'suite.json',{'pid':os.getpid(),'heartbeat':time.time(),'active':active,'completed':finished,'orphaned':orphaned,'total':10,'status':'running' if active or pending else 'finished'})
        for child in children:child.poll()
        if not active and not pending:break
        time.sleep(1)
    return 1 if orphaned else 0

if __name__=='__main__':raise SystemExit(main())
