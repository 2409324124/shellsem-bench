"""Independent functional fixtures; model code runs only in fresh local Docker sandboxes."""
import hashlib,json,re,subprocess,time
from pathlib import Path
from runner.sandbox import Sandbox

ROOT=Path(__file__).resolve().parents[2]
BASH=ROOT/'.runtime/bash-5.2.37/bin/bash'
CASES=[
 ('empty',[],b'',0,[],False),
 ('one',[b'a'],b'',0,[0],False),
 ('empty_record',[b''],b'',0,[0],False),
 ('hostile',[b' a\n\t\\*\'"',b'-x'],b'',0,[0,0],False),
 ('binary',[bytes([1,127,128,255])],b'',0,[0],False),
 ('worker_failure',[b'a',b'b',b'c'],b'',0,[7,9,0],False),
 ('scanner_failure',[b'a'],b'',37,[0],False),
 ('scanner_immediate',[],b'',126,[],False),
 ('tail_only',[],b'bad',0,[],False),
 ('tail_after_record',[b'a'],b'bad',0,[0],False),
 ('all_errors',[b'a',b'b'],b'bad',37,[9,7],False),
 ('framing_over_worker',[b'a'],b'bad',0,[23],False),
 ('worker255',[b'a'],b'',0,[255],False),
 ('max_record',[b'x'*8192],b'',0,[0],False),
 ('many',[f'r{i}'.encode() for i in range(30)],b'',0,[0]*30,False),
 ('streaming',[b'first',b'second'],b'',0,[0,0],True),
]
SCANNER=r'''#!/usr/local/bin/bash
printf '%s\0' "$@" > /fixture/scanner.args
printf '%s\n' "$$" > /fixture/scanner.pid
readlink /proc/$$/fd/1 > /fixture/scanner.pipe
if IFS= read -r -t 0.1 z; then r=0; else r=$?; fi
printf '%s\n' "$r" > /fixture/scanner.stdin
for f in /fixture/records/*; do
  [[ -f $f ]] || continue
  cat -- "$f"; printf '\0'
  if [[ -f /fixture/streaming && $f == */000 ]]; then
    for ((t=0;t<100;t++)); do [[ -f /fixture/worker.0.done ]] && break; sleep 0.02; done
    [[ -f /fixture/worker.0.done ]] || { printf blocked > /fixture/streaming_failed; exit 88; }
  fi
done
cat /fixture/tail
exit "$(</fixture/scanner.rc)"
'''
WORKER=r'''#!/usr/local/bin/bash
if ! mkdir /fixture/worker.lock 2>/dev/null; then printf overlap > /fixture/concurrent; fi
n=$(</fixture/count)
printf '%s' "$((n+1))" > /fixture/count
printf '%s\0' "$@" > "/fixture/worker.$n.args"
if IFS= read -r -t 0.1 z; then r=0; else r=$?; fi
printf '%s\n' "$r" > "/fixture/worker.$n.stdin"
pipe=$(</fixture/scanner.pipe)
for f in /proc/$$/fd/*; do
  if [[ $(readlink "$f") == "$pipe" ]]; then printf leak > /fixture/fd_leak; fi
done
cat "/fixture/stdout.$n"
cat "/fixture/stderr.$n" >&2
printf done > "/fixture/worker.$n.done"
rmdir /fixture/worker.lock 2>/dev/null || :
exit "$(<"/fixture/rc.$n")"
'''


def extract(raw):
    blocks=re.findall(r'```(?:bash|sh)?\s*\n(.*?)```',raw,re.S)
    candidates=[b for b in blocks if re.search(r'collect\s*\(\s*\)',b)]
    return candidates[-1] if candidates else raw


def grade(directory,source_name=None):
    directory=Path(directory);source=directory/(source_name or 'first-answer.txt')
    if not source.exists() and source_name is None:source=directory/'collect.artifact.sh'
    raw=source.read_text()
    code=extract(raw);(directory/'submission.sh').write_text(code)
    rows=[]
    for name,records,tail,scan_rc,worker_rcs,stream in CASES:
        for mode in ('direct','if'):
            d=directory/'verification'/f'{name}-{mode}';d.mkdir(parents=True,exist_ok=False)
            s=Sandbox(d).start()
            try:
                s.put('/usr/local/bin/bash',BASH.read_bytes(),'755')
                s.exec(['bash','-c','mkdir -p /fixture/records; chmod 777 /fixture /fixture/records'],user='0')
                s.put('/workspace/submission.sh',code)
                s.put('/usr/local/bin/scanner',SCANNER,'755');s.put('/usr/local/bin/worker',WORKER,'755')
                s.put('/fixture/count','0');s.put('/fixture/scanner.rc',str(scan_rc));s.put('/fixture/tail',tail)
                if stream:s.put('/fixture/streaming','1')
                stdout=b'';stderr=b''
                for i,(record,rc) in enumerate(zip(records,worker_rcs)):
                    a=b'O\0'+bytes([i%256])+b'\xff\n\n';b=b'E\0'+bytes([i%256])+b'\x80\n\n'
                    stdout+=a;stderr+=b
                    s.put(f'/fixture/records/{i:03}',record);s.put(f'/fixture/stdout.{i}',a);s.put(f'/fixture/stderr.{i}',b);s.put(f'/fixture/rc.{i}',str(rc))
                s.exec(['bash','-c','chmod -R a+rw /fixture'],user='0')
                pre="""set -Eeuo pipefail
shopt -u lastpipe inherit_errexit
set +m
export LC_ALL=C
exec 3>/fixture/report
source /workspace/submission.sh
printf '%s\\n' /proc/$$/fd/* > /fixture/fd_before
sleep 4 </dev/null >/dev/null 2>&1 &
caller_job=$!
"""
                call='collect "$1"\n' if mode=='direct' else 'if collect "$1"; then rc=0; else rc=$?; fi\nprintf \'%s\\n\' /proc/$$/fd/* > /fixture/fd_after\nexit "$rc"\n'
                s.put('/workspace/invoke.sh',pre+call)
                started=time.monotonic()
                try:
                    r=s.exec(['timeout','-k','1','3','bash','--noprofile','--norc','/workspace/invoke.sh',' root\n* '],input=b'CALLER_INPUT\n',timeout=5,check=False)
                    observed_rc=r.returncode;out=r.stdout;err=r.stderr
                except subprocess.TimeoutExpired:
                    observed_rc=124;out=b'';err=b''
                elapsed=time.monotonic()-started
                def read(p):
                    x=s.exec(['cat',p],check=False);return x.stdout if x.returncode==0 else None
                first=next((x for x in worker_rcs if x),0);frame=65 if tail else 0
                checks={'exit_code':observed_rc==(scan_rc or frame or first),
                    'stdout':out==stdout,'stderr':err==stderr,
                    'report':read('/fixture/report')==f'count={len(records)} scan={scan_rc} worker={first} framing={frame}\n'.encode(),
                    'scanner_args':read('/fixture/scanner.args')==b'--\0 root\n* \0',
                    'scanner_stdin_eof':read('/fixture/scanner.stdin')==b'1\n',
                    'worker_count':read('/fixture/count')==str(len(records)).encode(),
                    'worker_args':all(read(f'/fixture/worker.{i}.args')==b'--\0'+v+b'\0' for i,v in enumerate(records)),
                    'worker_stdin_eof':all(read(f'/fixture/worker.{i}.stdin')==b'1\n' for i in range(len(records))),
                    'no_scanner_fd_in_worker':read('/fixture/fd_leak') is None,
                    'sequential_workers':read('/fixture/concurrent') is None,
                    'streaming':read('/fixture/streaming_failed') is None,
                    'no_wait_for_caller_job':elapsed<3,
                }
                if mode=='if':checks['fds_closed']=read('/fixture/fd_before')==read('/fixture/fd_after')
                (d/'stdout.bin').write_bytes(out);(d/'stderr.bin').write_bytes(err)
                row={'case':name,'mode':mode,'passed':all(checks.values()),'checks':checks,'exit_code':observed_rc,'elapsed':round(elapsed,3)}
                rows.append(row);(d/'result.json').write_text(json.dumps(row,indent=2)+'\n')
            finally:s.remove()
    summary={'passed':sum(r['passed'] for r in rows),'total':len(rows),'cases':rows,
             'source_sha256':hashlib.sha256(code.encode()).hexdigest(),'submission_source':source.name,'constraint_review':'manual, reported separately','extraction_policy':'unmodified saved function file; response format reviewed separately' if source.name=='collect.artifact.sh' else 'last complete collect code block within the original first response; no repair',
             'fixture_origin':'independently constructed; original reference package was not supplied'}
    (directory/'grade.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(directory.name,summary['passed'],'/',summary['total'],flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directories',nargs='+');parser.add_argument('--source',choices=['first-answer.txt','collect.artifact.sh']);args=parser.parse_args()
    for p in args.directories:grade(p,args.source)
