import subprocess
import time
from verifier.support import octal


def processes(s):
    rows=[]
    for line in s.exec(['ps','-eo','uid=,pid=,ppid=,pgid=,stat=,args='],user='0').stdout.decode().splitlines():
        fields=line.strip().split(None,5)
        if len(fields)==6:
            rows.append({'uid':int(fields[0]),'pid':int(fields[1]),'ppid':int(fields[2]),'pgid':int(fields[3]),'stat':fields[4],'args':fields[5]})
    return rows


def cases():
    for name in ('success','worker_failure','sigterm_tree','sigint_tree','early_parent_fd','unrelated_sentinel'):
        payloads=[f'out{i}'.encode()+b'\0\n\n' for i in range(4)]
        errors=[f'err{i}'.encode()+b'\0' for i in range(4)]
        state={'peak':0,'released':False,'signaled':False,'signal_at':None,'sentinel':None,'atomic':True,'residuals':[]}
        def setup(s,name=name,payloads=payloads,errors=errors,state=state):
            # Explicit join avoids octal/string escape ambiguity.
            s.put('/fixture/tasks.nul',b''.join(str(i).encode()+b'\0' for i in range(4)))
            body='#!/bin/bash\nif [[ $1 == --sentinel ]]; then while :; do sleep 1; done; fi\nwhile [[ ! -e /fixture/release ]]; do sleep .03; done\ncase "$2" in\n'
            for i in range(4):
                body+=f'{i}) printf \'{octal(payloads[i])}\'; printf \'{octal(errors[i])}\' >&2;\n'
                if name=='success':body+='sleep .2; exit 0;;\n'
                elif name=='early_parent_fd':body+='sleep 8 &\nexit 0;;\n'
                elif name=='worker_failure' and i==1:body+='sleep .15; exit 37;;\n'
                else:body+='trap "" TERM\nbash -c \'trap "" TERM; sleep 999 & wait\' &\nwait;;\n'
            body+='*) exit 125;;\nesac\n'
            s.put('/usr/local/bin/worker',body,'755')
            if name=='unrelated_sentinel':
                state['sentinel']=subprocess.Popen(['docker','exec','--user','1001:1001',s.name,'setsid','/usr/local/bin/worker','--sentinel'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return ['/fixture/tasks.nul','/workspace/out']
        def monitor(s,elapsed,observations,name=name,state=state,payloads=payloads):
            rows=processes(s)
            count=sum('/bin/bash /usr/local/bin/worker -- ' in r['args'] for r in rows)
            state['peak']=max(state['peak'],count)
            if not state['released'] and (count>=4 or elapsed>2):s.put('/fixture/release',b'');state['released']=True;state['released_at']=elapsed
            target='INT' if name=='sigint_tree' else 'TERM'
            if name in ('sigterm_tree','sigint_tree','unrelated_sentinel') and state['released'] and elapsed-state['released_at']>.25 and not state['signaled']:
                main=next((r for r in rows if r['args'].startswith('bash /workspace/solution.sh ')),None)
                if main:s.exec(['kill','-'+target,str(main['pid'])]);state['signaled']=True;state['signal_at']=elapsed
            if s.exec(['test','-e','/workspace/out'],check=False).returncode==0:
                got=s.exec(['cat','/workspace/out/aggregate.bin'],check=False)
                if got.returncode or got.stdout!=b''.join(payloads):state['atomic']=False
            if not observations or observations[-1]['workers']!=count:observations.append({'at':round(elapsed,3),'workers':count,'signal_sent':state['signaled']})
        def check(s,r,name=name,state=state,payloads=payloads,errors=errors):
            expected=37 if name=='worker_failure' else 130 if name=='sigint_tree' else 143 if name in ('sigterm_tree','unrelated_sentinel') else 0
            if r['timeout']:return False
            sentinel_ok=True
            # Inspect before Docker cleanup. Tolerate only short zombie reaping, not live stragglers.
            deadline=time.monotonic()+.3
            while True:
                rows=processes(s)
                sentinel_groups={row['pgid'] for row in rows if '/worker --sentinel' in row['args']}
                if name=='unrelated_sentinel':sentinel_ok=bool(sentinel_groups)
                residues=[row for row in rows if row['uid']==1001 and row['pgid'] not in sentinel_groups and not row['stat'].startswith('Z')]
                if not residues or time.monotonic()>deadline:break
                time.sleep(.05)
            state['residuals']=residues
            r['observations'].append({'live_residuals':residues,'sentinel_alive':sentinel_ok,'atomic':state['atomic']})
            if r['rc']!=expected or residues or not sentinel_ok or not state['atomic'] or state['peak']!=4:return False
            if expected:
                if expected in (130,143) and (not state['signaled'] or r['elapsed']-state['signal_at']>2):return False
                return s.exec(['test','!','-e','/workspace/out'],check=False).returncode==0
            return s.get('/workspace/out/aggregate.bin')==b''.join(payloads) and all(s.get(f'/workspace/out/stderr/{i:06d}.log')==errors[i] for i in range(4))
        def cleanup(state=state):
            if state['sentinel'] is not None:
                try:state['sentinel'].wait(timeout=3)
                except subprocess.TimeoutExpired:state['sentinel'].kill();state['sentinel'].wait()
        yield {'name':name,'setup':setup,'monitor':monitor,'check':check,'limit':8,'cleanup':cleanup}
