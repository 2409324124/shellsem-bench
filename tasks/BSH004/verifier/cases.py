import shlex
from verifier.support import octal


def fixture(s,tasks,codes,payloads,errors,delays):
    s.put('/fixture/tasks.nul',b''.join(t.encode()+b'\0' for t in tasks))
    body='#!/bin/bash\nset -e\n[[ $1 == -- ]] || exit 125\ncase "$2" in\n'
    for i,t in enumerate(tasks):
        s.put(f'/fixture/out{i}',payloads[i]);s.put(f'/fixture/err{i}',errors[i])
        body+=f'{shlex.quote(t)}) while [[ ! -e /fixture/release ]]; do sleep .03; done; sleep {delays[i]}; cat /fixture/out{i}; cat /fixture/err{i} >&2; exit {codes[i]};;\n'
    body+='*) exit 125;;\nesac\n'
    s.put('/usr/local/bin/worker',body,'755')


def cases():
    for name,n,fail,large in [('empty',0,{},False),('ordered',8,{},False),('first_input_failure',8,{1:37,6:8},False),('hostile',4,{},False),('binary_pressure',4,{},True),('single_failure',1,{0:126},False)]:
        tasks=[f'task {i}\n*' for i in range(n)]
        codes=[fail.get(i,0) for i in range(n)]
        payloads=[(bytes(range(256))*512 if large else f'out{i}'.encode())+b'\0\n\n' for i in range(n)]
        errors=[(b'e'*131072 if large else b'error')+str(i).encode()+b'\0' for i in range(n)]
        state={'peak':0,'released':False,'atomic':True}
        def setup(s,tasks=tasks,codes=codes,payloads=payloads,errors=errors):
            fixture(s,tasks,codes,payloads,errors,[.45 if i%4==1 else .1 for i in range(len(tasks))])
            return ['/fixture/tasks.nul','/workspace/out']
        def monitor(s,elapsed,observations,state=state,n=n,payloads=payloads,codes=codes):
            if s.exec(['test','-e','/workspace/out'],check=False).returncode==0:
                got=s.exec(['cat','/workspace/out/aggregate.bin'],check=False)
                if any(codes) or got.returncode or got.stdout!=b''.join(payloads):state['atomic']=False
            ps=s.exec(['ps','-eo','pid,args'],user='0').stdout.decode()
            count=sum('/bin/bash /usr/local/bin/worker -- ' in row for row in ps.splitlines())
            state['peak']=max(state['peak'],count)
            if not state['released'] and (count>=min(n,4) or elapsed>2):
                s.put('/fixture/release',b'');state['released']=True
            if not observations or observations[-1]['workers']!=count:observations.append({'at':round(elapsed,3),'workers':count})
        def check(s,r,codes=codes,payloads=payloads,errors=errors,state=state,n=n):
            expected=next((c for c in codes if c),0)
            if r['timeout'] or r['rc']!=expected or not state['atomic'] or state['peak']>4 or (n>=4 and state['peak']<4):return False
            if expected:return s.exec(['test','!','-e','/workspace/out'],check=False).returncode==0
            return s.get('/workspace/out/aggregate.bin')==b''.join(payloads) and all(s.get(f'/workspace/out/stderr/{i:06d}.log')==errors[i] for i in range(n))
        yield {'name':name,'setup':setup,'monitor':monitor,'check':check,'limit':10}
