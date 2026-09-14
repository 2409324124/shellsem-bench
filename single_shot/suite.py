"""Run the Pi comparison serially after the tool-free results are frozen."""
import json,os,subprocess,sys,time
from pathlib import Path
from runner.state import atomic_json,read_json
ROOT=Path(__file__).resolve().parents[1]

def main():
    for p in [ROOT/'runs/single-shot/2026-09-14-first/baseline-Q2/grade.json',ROOT/'runs/single-shot/2026-09-14-transport-retry/preview-Q2/grade.json']:
        if not p.exists():raise RuntimeError('Finish bare-model grading first')
    ids=[(task,label,f'pi-compare-20260914-{label}-{task}') for task in ('Q1','Q2') for label in ('preview','baseline')]
    if any((ROOT/'runs'/name).exists() for _,_,name in ids):raise RuntimeError('Comparison directory exists; do not overwrite or rerun')
    completed=[]
    for task,label,name in ids:
        run=ROOT/'runs'/name
        with (ROOT/'runs/pi-compare-launch.log').open('ab') as log:
            child=subprocess.Popen([sys.executable,'-m','runner.guard','--run-dir',str(run),'--deadline-seconds','600','--',sys.executable,'-m','single_shot.pi','--task',task,'--label',label],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
        while child.poll() is None:
            atomic_json(ROOT/'runs/suite.json',{'pid':os.getpid(),'heartbeat':time.time(),'active':[name],'completed':completed,'orphaned':[],'total':4,'concurrency':1,'status':'running','mode':'pi_comparison'})
            time.sleep(1)
        completed.append(name)
        print(name,read_json(run/'result.json').get('status'),flush=True)
    atomic_json(ROOT/'runs/suite.json',{'pid':os.getpid(),'heartbeat':time.time(),'active':[],'completed':completed,'orphaned':[],'total':4,'concurrency':1,'status':'finished','mode':'pi_comparison'})

if __name__=='__main__':main()
