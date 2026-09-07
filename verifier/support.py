import io
import tarfile
import time
import subprocess
from pathlib import Path
from runner.state import heartbeat


def tree(s, files, root='/fixture/input'):
    s.exec(['mkdir','-p',root],user='0')
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w') as t:
        for name,data in files.items():
            entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o644
            t.addfile(entry,io.BytesIO(data))
    s.exec(['tar','--no-same-owner','-xf','-','-C',root],input=buf.getvalue(),user='0')


def execute(s,args,run_dir,case,monitor=None,limit=12):
    run_dir=Path(run_dir);case_dir=run_dir/'cases'/case;case_dir.mkdir(parents=True,exist_ok=True);out=case_dir/'stdout.bin';err=case_dir/'stderr.bin'
    start=time.monotonic(); observations=[];timed_out=False
    with out.open('wb') as o,err.open('wb') as e:
        p=subprocess.Popen(['docker','exec','--user','1001:1001','--workdir','/workspace',s.name,'bash','/workspace/solution.sh',*args],stdout=o,stderr=e)
        try:
            while p.poll() is None:
                heartbeat(run_dir,'verifying',case=case,container=s.name,elapsed=time.monotonic()-start)
                if monitor: monitor(s,time.monotonic()-start,observations)
                if time.monotonic()-start>limit or out.stat().st_size+err.stat().st_size>8388608:
                    timed_out=True;s.remove();p.kill();break
                time.sleep(.05)
            p.wait(timeout=3)
        finally:
            if p.poll() is None:p.kill();p.wait()
    return {'rc':p.returncode,'stdout':out.read_bytes(),'stderr':err.read_bytes(),'timeout':timed_out,'elapsed':time.monotonic()-start,'observations':observations}


def octal(data):return ''.join('\\%03o'%b for b in data)
