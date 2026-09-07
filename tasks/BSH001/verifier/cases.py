import hashlib
from verifier.support import tree


def cases():
    datasets=[('empty',{}),('hostile',{'a\nb':b'abc','a':b'', '-leading':b'\0\xff\n','*?[]':b'test',"'\"\\\t":b'xyz','$(touch PWNED)':b'never execute','中文.txt':b'utf8'}),
        ('nested',{'d/z':b'last','d/a':b'first','a':b'root'}),('binary',{'all-bytes':bytes(range(256))*256,'newlines':b'\n'*10}),
        ('many',{f'{n:03d} x':str(n).encode() for n in range(40)}),('missing',None)]
    for name,files in datasets:
        def setup(s,files=files):
            if files is not None:tree(s,files)
            return ['/fixture/input']
        expected=b'' if files is None else b''.join(p.encode()+b'\0'+str(len(files[p])).encode()+b'\0'+hashlib.sha256(files[p]).hexdigest().encode()+b'\0' for p in sorted(files,key=lambda p:p.encode()))
        def check(s,r,files=files,expected=expected):
            return not r['timeout'] and ((r['rc']!=0) if files is None else r['rc']==0 and r['stdout']==expected)
        yield {'name':name,'setup':setup,'check':check}
