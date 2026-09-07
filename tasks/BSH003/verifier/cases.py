from verifier.support import octal


def cases():
    inputs=[('empty',[],0,0),('many',[str(i).encode() for i in range(10000)],0,0),('newlines',[b'\n',b'',b'foo\nbar',b'\xff\t\n'],0,0),('partial_failure',[b'valid']*20,37,0),('immediate_failure',[],126,0),('delayed_failure',[b'x'*100]*1000,37,.2)]
    for name,records,rc,delay in inputs:
        state={'atomic':True}
        raw=b''.join(x+b'\0' for x in records)
        expected=b''.join(str(len(x)).encode()+b'\0'+x+b'\0' for x in records)
        def setup(s,raw=raw,rc=rc,delay=delay):
            s.put('/fixture/records',raw)
            s.put('/usr/local/bin/scanner',f'#!/bin/bash\ncat /fixture/records\nsleep {delay}\nexit {rc}\n','755')
            return ['/fixture','/workspace/out']
        def monitor(s,elapsed,observations,state=state,expected=expected,rc=rc):
            if s.exec(['test','-e','/workspace/out'],check=False).returncode==0:
                got=s.exec(['cat','/workspace/out/manifest.bin'],check=False)
                if rc or got.returncode or got.stdout!=expected:state['atomic']=False
        def check(s,r,expected=expected,rc=rc,records=records,state=state):
            if r['timeout'] or r['rc']!=rc or not state['atomic']:return False
            if rc:return s.exec(['test','!','-e','/workspace/out'],check=False).returncode==0
            return s.get('/workspace/out/manifest.bin')==expected and s.get('/workspace/out/count.txt')==str(len(records)).encode()+b'\n'
        yield {'name':name,'setup':setup,'check':check,'monitor':monitor}
