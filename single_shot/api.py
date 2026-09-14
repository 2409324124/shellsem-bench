"""Four independent, serial, tool-free first responses. No Pi or retries."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from runner.config import load_config
from runner.probe import NoRedirect
from runner.state import atomic_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tasks',nargs='+',choices=['Q1','Q2'],default=['Q1','Q2'])
    p.add_argument('--labels',nargs='+',choices=['preview','baseline'],default=['preview','baseline'])
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((ROOT/'single_shot/manifest.json').read_text())
    opener=urllib.request.build_opener(NoRedirect)
    for task in manifest['tasks']:
        if task['id'] not in args.tasks:continue
        prompt=(ROOT/'single_shot'/task['prompt']).read_bytes()
        assert hashlib.sha256(prompt).hexdigest()==task['sha256']
        for label,env in [('preview','.env'),('baseline','.env.baseline')]:
            if label not in args.labels:continue
            c=load_config(ROOT/env)
            d=args.output/f"{label}-{task['id']}";d.mkdir()
            payload={'model':c.model_id,'messages':[{'role':'user','content':prompt.decode()}],
                     'max_tokens':8192,'enable_thinking':False,'stream':False}
            atomic_json(d/'request.json',payload)
            (d/'prompt.md').write_bytes(prompt)
            metadata={'task':task['id'],'label':label,'requested_model':c.model_id,'endpoint':c.base_url,
                      'prompt_sha256':task['sha256'],'started_at':time.time(),'status':'requesting',
                      'api':True,'pi':False,'tools_provided':False,'attempt':1,'retries':0}
            atomic_json(d/'capture.json',metadata)
            print(json.dumps({'run':d.name,'status':'requesting'}),flush=True)
            started=time.monotonic()
            request=urllib.request.Request(c.base_url+'/chat/completions',data=json.dumps(payload).encode(),
                headers={'Authorization':'Bearer '+c.api_key,'Content-Type':'application/json'})
            try:
                with opener.open(request,timeout=120) as response:
                    raw=response.read(8*1024*1024+1)
                    (d/'response.raw.json').write_bytes(raw)
                    if len(raw)>8*1024*1024:raise ValueError('response_size_limit')
                    result=json.loads(raw)
                choice=result['choices'][0];message=choice['message'];answer=message.get('content')
                if not isinstance(answer,str):raise ValueError('missing_text_answer')
                (d/'first-answer.txt').write_bytes(answer.encode())
                metadata.update(status='captured',response_model=result.get('model'),response_id=result.get('id'),
                    finish_reason=choice.get('finish_reason'),usage=result.get('usage'),
                    first_answer_sha256=hashlib.sha256(answer.encode()).hexdigest(),
                    unexpected_tool_calls=bool(message.get('tool_calls')),grading_status='not_started')
            except urllib.error.HTTPError as e:
                (d/'http-error.txt').write_bytes(e.read(65536))
                metadata.update(status='api_error',http_status=e.code)
            except Exception as e:
                metadata.update(status='api_error',error_type=type(e).__name__,error=str(e).replace(c.api_key,'[REDACTED]'))
            metadata.update(elapsed_seconds=round(time.monotonic()-started,3),finished_at=time.time())
            atomic_json(d/'capture.json',metadata)
            for f in d.iterdir():f.chmod(0o444)
            print(json.dumps({'run':d.name,**{k:metadata[k] for k in ('status','elapsed_seconds','finish_reason') if k in metadata}}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
