import importlib
from pathlib import Path
from runner.sandbox import Sandbox,CandidateOutputError
from runner.state import heartbeat, atomic_json
from verifier.support import execute


def evaluate(task,solution,run_dir,only_cases=None):
    module=importlib.import_module(f'tasks.{task}.verifier.cases')
    rows=[]
    for case in module.cases():
        if only_cases is not None and case['name'] not in only_cases:continue
        heartbeat(run_dir,'case_setup',task=task,case=case['name'])
        s=Sandbox(run_dir).start()
        try:
            s.put('/workspace/solution.sh',solution,'755')
            args=case['setup'](s)
            r=execute(s,args,run_dir,case['name'],case.get('monitor'),case.get('limit',12))
            try:passed=case['check'](s,r)
            except CandidateOutputError:passed=False
            row={'case':case['name'],'passed':bool(passed),'rc':r['rc'],'timeout':r['timeout'],'elapsed':round(r['elapsed'],3),
                'stdout_bytes':len(r['stdout']),'stderr_tail':r['stderr'][-2000:].decode(errors='replace'),'observations':r['observations']}
            rows.append(row)
            atomic_json(Path(run_dir)/'verifier-progress.json',{'task':task,'cases':rows})
        finally:
            s.remove()
            if case.get('cleanup'):case['cleanup']()
    return rows
