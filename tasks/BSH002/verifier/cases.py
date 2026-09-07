from verifier.support import octal


def cases():
    for label,rcs,broken in [('ok',(0,0,0),False),('source_failure',(37,0,0),False),('priority',(0,2,23),False),('all_failure',(126,37,1),False),('explicit_141',(141,0,0),False),('sigpipe',(141,141,23),True)]:
        payload=bytes(range(256))*1024+b'\n\n\n'
        def setup(s,rcs=rcs,broken=broken):
            s.exec(['mkdir','/workspace/out'])
            for i,name in enumerate(('source','filter','sink')):
                body=f"#!/bin/bash\nset -e\nprintf '{name}\\0\\n' >&2\n"
                if i==0:body+=('while :; do printf "%4096s" x; done\n' if broken else "printf '"+octal(payload)+"'\n")
                elif not (i==2 and broken):body+='cat\n'
                body+=f'exit {rcs[i]}\n'
                s.put('/usr/local/bin/'+name+'-stage',body,'755')
            return ['/workspace/out']
        pipeline=next((n for n in rcs[::-1] if n),0)
        final=next((rcs[i] for i in (1,0,2) if rcs[i]),0)
        expected=f'source_rc={rcs[0]}\nfilter_rc={rcs[1]}\nsink_rc={rcs[2]}\npipeline_rc={pipeline}\n'.encode()
        def check(s,r,expected=expected,final=final,broken=broken):
            if r['timeout'] or r['rc']!=final or r['stdout']!=expected:return False
            if s.get('/workspace/out/stdout.bin')!=(b'' if broken else payload):return False
            return all(s.get('/workspace/out/'+name+'.stderr')==name.encode()+b'\0\n' for name in ('source','filter','sink'))
        yield {'name':label,'setup':setup,'check':check}
