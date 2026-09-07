"""One guarded model/task run; the observer never runs inside this process."""
import argparse
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
from runner.config import load_config
from runner.sandbox import Sandbox,docker
from runner.state import heartbeat,atomic_json
from verifier.evaluate import evaluate

ROOT=Path(__file__).resolve().parents[1]


def run(task,label,run_dir,limit):
    config=load_config(ROOT/('.env' if label=='preview' else '.env.baseline'))
    heartbeat(run_dir,'starting',task=task,label=label,last_activity=time.time())
    s=Sandbox(run_dir).start()
    result={'task':task,'label':label,'requested_model':config.model_id,'status':'infrastructure_error'}
    try:
        image=json.loads(docker('inspect',s.name).stdout)[0]
        atomic_json(run_dir/'container-config.json',{'image_id':image['Image'],'host_config':image['HostConfig'],'container':s.name})
        prompt=ROOT/'tasks'/task/'prompt.md'
        s.put('/workspace/prompt.md',prompt.read_bytes())
        s.put('/workspace/public-test.sh',(ROOT/'tasks'/task/'public/test.sh').read_bytes(),'755')
        # Public helpers are deliberately distinct from hidden implementations.
        helpers=ROOT/'tasks'/task/'public/bin'
        if helpers.exists():
            for helper in helpers.iterdir():s.put('/usr/local/bin/'+helper.name,helper.read_bytes(),'755')
        cfg=run_dir/'pi-config';cfg.mkdir(exist_ok=True)
        model={'id':config.model_id,'reasoning':True,'input':['text'],'contextWindow':32768,'maxTokens':4096,'samplingParams':{'enable_thinking':False},
            'compat':{'supportsStore':False,'supportsDeveloperRole':False,'supportsReasoningEffort':False,'maxTokensField':'max_tokens'}}
        atomic_json(cfg/'models.json',{'providers':{'qwen-bench':{'baseUrl':config.base_url,'api':'openai-completions','apiKey':'$QWEN_API_KEY','models':[model]}}})
        env=os.environ.copy();env.update(QWEN_API_KEY=config.api_key,QWEN_MODEL_ID=config.model_id,PI_OFFLINE='1')
        cmd=['node',str(ROOT/'runner/pi_agent.mjs'),'run',s.name,str(cfg),str(prompt)]
        process=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        sel=selectors.DefaultSelector();sel.register(process.stdout,selectors.EVENT_READ,'stdout');sel.register(process.stderr,selectors.EVENT_READ,'stderr')
        start=time.monotonic();activity=time.time();buffers={'stdout':b'','stderr':b''};events_count=0;tool=None;budget=False;last_stats=0;stats={};tool_ids=set();usage={'input':0,'output':0,'reasoning':0,'cacheRead':0}
        with (run_dir/'events.jsonl').open('w') as log:
            while sel.get_map():
                elapsed=time.monotonic()-start
                if elapsed>limit or log.tell()>33554432:
                    budget=True;process.kill();
                    partial=s.exec(['head','-c','1048576','/workspace/solution.sh'],check=False)
                    if partial.returncode==0:(run_dir/'solution.partial.sh').write_bytes(partial.stdout)
                    s.remove();break
                for key,_ in sel.select(.1):
                    data=os.read(key.fileobj.fileno(),65536)
                    if not data:sel.unregister(key.fileobj);continue
                    activity=time.time();buffers[key.data]+=data
                    while b'\n' in buffers[key.data]:
                        line,buffers[key.data]=buffers[key.data].split(b'\n',1)
                        text=line.decode(errors='replace').replace(config.api_key,'[REDACTED]')
                        try:event=json.loads(text)
                        except ValueError:event={'type':'controller_stderr','text':text}
                        if event.get('type')=='tool_execution_start':
                            tool={'name':event.get('toolName'),'args':event.get('args'),'started_at':time.time()};tool_ids.add(event.get('toolCallId'))
                        elif event.get('type')=='tool_execution_end':tool=None
                        if event.get('type')=='message_end' and event.get('message',{}).get('role')=='assistant':
                            for metric in usage:usage[metric]+=event['message'].get('usage',{}).get(metric,0)
                        if event.get('type')=='effective_configuration':atomic_json(run_dir/'effective-config.json',event)
                        log.write(json.dumps(event,ensure_ascii=False)+'\n');log.flush();events_count+=1
                if elapsed-last_stats>3:
                    try:
                        stats={'processes':s.processes(), 'docker':docker('stats','--no-stream','--format','{{json .}}',s.name,timeout=3).stdout.decode(errors='replace')}
                    except Exception as exc:stats={'observation_error':type(exc).__name__}
                    last_stats=elapsed
                heartbeat(run_dir,'generating',task=task,label=label,container=s.name,controller_pid=process.pid,last_activity=activity,
                    elapsed=round(elapsed,1),remaining_seconds=max(0,round(limit-elapsed,1)),active_tool=tool,events=events_count,resources=stats,tool_calls=len(tool_ids),usage=usage)
            process.wait(timeout=4)
        result.update(generation_seconds=round(time.monotonic()-start,3),tool_calls=len(tool_ids),usage=usage)
        if budget:result['status']='generation_budget_exceeded';return result
        if process.returncode:result['status']='generation_error';result['controller_rc']=process.returncode;return result
        solution=s.exec(['head','-c','1048577','/workspace/solution.sh'],check=False)
        if solution.returncode or len(solution.stdout)>1048576:result['status']='missing_or_oversized_submission';return result
        (run_dir/'solution.sh').write_bytes(solution.stdout)
        s.remove()
        verification_start=time.monotonic()
        rows=evaluate(task,solution.stdout,run_dir)
        result['verification_seconds']=round(time.monotonic()-verification_start,3)
        result.update(status='pass' if all(row['passed'] for row in rows) else 'fail',cases=rows)
        return result
    finally:s.remove()


def main():
    p=argparse.ArgumentParser();p.add_argument('--task',choices=[f'BSH00{i}' for i in range(1,6)],required=True);p.add_argument('--label',choices=['preview','baseline'],required=True);p.add_argument('--limit',type=float,default=300);args=p.parse_args()
    run_dir=Path(os.environ['SHELLSEM_RUN_DIR']).resolve();run_dir.mkdir(parents=True,exist_ok=True)
    try:result=run(args.task,args.label,run_dir,args.limit)
    except Exception as exc:result={'task':args.task,'label':args.label,'status':'infrastructure_error','error_type':type(exc).__name__,'error':str(exc)[:1500]}
    atomic_json(run_dir/'result.json',result)
    heartbeat(run_dir,'finished',task=args.task,label=args.label,result_status=result['status'])
    return 1 if result['status']=='infrastructure_error' else 0

if __name__=='__main__':raise SystemExit(main())
