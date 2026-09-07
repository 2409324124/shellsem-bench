"""No pulls or daemon reconfiguration: resource-limited local Docker containers."""
from pathlib import Path
import subprocess
import time
import uuid
from runner.state import atomic_json, read_json

IMAGE='wcb/ps7-sidecar:7.6.4'

class CandidateOutputError(Exception): pass


def docker(*args, input=None, timeout=8, check=True):
    r=subprocess.run(['docker',*map(str,args)],input=input,capture_output=True,timeout=timeout)
    if check and r.returncode:
        raise RuntimeError('docker '+str(args[0])+': '+r.stderr.decode(errors='replace')[:1000])
    return r


class Sandbox:
    def __init__(self, run_dir, image=IMAGE):
        self.run_dir=Path(run_dir)
        self.name='shellsem-'+uuid.uuid4().hex[:16]
        self.image=image
    def start(self):
        names=read_json(self.run_dir/'containers.json').get('names',[])
        names.append(self.name)
        atomic_json(self.run_dir/'containers.json',{'names':names})
        docker('run','--pull=never','-d','--name',self.name,'--label','shellsem.managed=true',
            '--network','bridge','--memory','512m','--memory-swap','512m','--cpus','1','--pids-limit','128',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
            '--tmpfs','/workspace:rw,exec,nosuid,size=128m,mode=1777',
            '--tmpfs','/tmp:rw,exec,nosuid,size=64m,mode=1777',
            '--tmpfs','/usr/local/bin:rw,exec,nosuid,size=8m,mode=0755',
            '--tmpfs','/fixture:rw,exec,nosuid,size=64m,mode=0755',
            '--env','LC_ALL=C','--workdir','/workspace','--entrypoint','/usr/bin/sleep',self.image,'infinity')
        return self
    def put(self,path,data,mode='644'):
        if isinstance(data,str):data=data.encode()
        self.exec(['bash','-c','cat > "$1" && chmod "$2" "$1"','_',path,mode],input=data,user='0')
    def exec(self,args,input=None,user='1001:1001',timeout=8,check=True):
        return docker('exec','-i','--user',user,'--workdir','/workspace',self.name,*args,input=input,timeout=timeout,check=check)
    def get(self,path):
        r=self.exec(['cat','--',path],check=False)
        if r.returncode:raise CandidateOutputError('Cannot read submitted output: '+path)
        return r.stdout
    def remove(self):docker('rm','-f',self.name,check=False)
    def processes(self):
        return docker('top',self.name,'-eo','pid,ppid,pgid,stat,etime,pcpu,pmem,args',check=False).stdout.decode(errors='replace')
