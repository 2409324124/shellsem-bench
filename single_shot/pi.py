"""A guarded Pi tool-enabled comparison using the same two semantic tasks."""
import argparse,json,os,selectors,subprocess,time
from pathlib import Path
from runner.config import load_config
from runner.sandbox import Sandbox
from runner.scoring import read_events,summarize
from runner.state import atomic_json,heartbeat

ROOT=Path(__file__).resolve().parents[1]


def run(task,label,directory,generation_seconds=300,max_tokens=8192,context_window=32768,max_tool_calls=100):
    c=load_config(ROOT/('.env' if label=='preview' else '.env.baseline'))
    prompt=ROOT/'single_shot/prompts_pi'/f'{task}.md'
    heartbeat(directory,'starting',task=task,label=label)
    s=Sandbox(directory).start();last=None;failure=None;tool_ids=set();process=None
    try:
        s.put('/usr/local/bin/bash',(ROOT/'.runtime/bash-5.2.37/bin/bash').read_bytes(),'755')
        s.put('/workspace/prompt.md',prompt.read_bytes())
        (directory/'prompt.md').write_bytes(prompt.read_bytes())
        cfg=directory/'pi-config';cfg.mkdir()
        model={'id':c.model_id,'reasoning':True,'input':['text'],'contextWindow':context_window,'maxTokens':max_tokens,'samplingParams':{'enable_thinking':False},'compat':{'supportsStore':False,'supportsDeveloperRole':False,'supportsReasoningEffort':False,'maxTokensField':'max_tokens'}}
        atomic_json(cfg/'models.json',{'providers':{'qwen-bench':{'baseUrl':c.base_url,'api':'openai-completions','apiKey':'$QWEN_API_KEY','models':[model]}}})
        env={**os.environ,'QWEN_API_KEY':c.api_key,'QWEN_MODEL_ID':c.model_id,'PI_OFFLINE':'1','SHELLSEM_REQUEST_ARCHIVE':str(directory/'requests'),'SHELLSEM_MAX_TOOL_CALLS':str(max_tool_calls)}
        process=subprocess.Popen(['node',str(ROOT/'runner/pi_agent.mjs'),'run',s.name,str(cfg),str(prompt)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        sel=selectors.DefaultSelector()
        for stream in (process.stdout,process.stderr):sel.register(stream,selectors.EVENT_READ)
        buffers={};start=time.monotonic();activity=time.time();active_tool=None;stats_time=0;resources={}
        with (directory/'events.jsonl').open('w') as log:
            while sel.get_map():
                elapsed=time.monotonic()-start
                if (generation_seconds and elapsed>generation_seconds) or log.tell()>33554432:
                    failure='generation_time_limit' if generation_seconds and elapsed>generation_seconds else 'event_log_limit';process.kill();break
                for key,_ in sel.select(.1):
                    data=os.read(key.fileobj.fileno(),65536)
                    if not data:sel.unregister(key.fileobj);continue
                    activity=time.time();buffers[key.fileobj]=buffers.get(key.fileobj,b'')+data
                    while b'\n' in buffers[key.fileobj]:
                        line,buffers[key.fileobj]=buffers[key.fileobj].split(b'\n',1)
                        line=line.decode(errors='replace').replace(c.api_key,'[REDACTED]')
                        try:e=json.loads(line)
                        except ValueError:e={'type':'controller_stderr','text':line}
                        log.write(json.dumps(e,ensure_ascii=False)+'\n');log.flush()
                        if e.get('type')=='message_end' and e.get('message',{}).get('role')=='assistant':last=e['message']
                        if e.get('type')=='effective_configuration':atomic_json(directory/'effective-config.json',e)
                        if e.get('type')=='tool_execution_start':tool_ids.add(e.get('toolCallId'));active_tool={'name':e.get('toolName'),'args':e.get('args')}
                        if e.get('type')=='tool_execution_end':active_tool=None
                if elapsed-stats_time>3:
                    resources={'processes':s.processes()};stats_time=elapsed
                heartbeat(directory,'generating',task=task,label=label,elapsed=round(elapsed,1),remaining_seconds=max(0,round(generation_seconds-elapsed,1)) if generation_seconds else None,controller_pid=process.pid,last_activity=activity,tool_calls=len(tool_ids),active_tool=active_tool,resources=resources)
            process.wait(timeout=5)
        sel.close();process.stdout.close();process.stderr.close()
        if not failure and process.returncode:failure='generation_error'
        result={'task':task,'label':label,'mode':'pi_tools','requested_model':c.model_id,'status':failure or 'captured','generation_seconds':round(time.monotonic()-start,3),'tool_calls':len(tool_ids),'generation_limit_seconds':generation_seconds,'max_tokens':max_tokens,'context_window':context_window,'max_tool_calls':max_tool_calls}
        if last:
            atomic_json(directory/'last-assistant.json',last)
            text=''.join(x.get('text','') for x in last.get('content',[]) if x.get('type')=='text')
            if text and last.get('stopReason') in ('stop','length'):
                (directory/'first-answer.txt').write_text(text)
                result['finish_reason']=last.get('stopReason')
        s.exec(['bash','-c','kill -STOP -1'],check=False)
        artifact=s.exec(['bash','-c','test -f /workspace/collect.sh && head -c 1048577 /workspace/collect.sh'],check=False)
        if not artifact.returncode and len(artifact.stdout)<=1048576:(directory/'collect.artifact.sh').write_bytes(artifact.stdout)
        if not (directory/'first-answer.txt').exists():
            result['answer_status']='missing_final_answer'
            if not failure:failure='missing_final_answer';result['status']=failure
        result['score']=summarize({'status':failure or 'pass'},read_events(directory/'events.jsonl'))
        atomic_json(directory/'result.json',result)
        heartbeat(directory,'finished',task=task,label=label,result_status=result['status'])
        return result
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait()
        s.remove()


def main():
    p=argparse.ArgumentParser();p.add_argument('--task',choices=['Q1','Q2'],required=True);p.add_argument('--label',choices=['preview','baseline'],required=True);p.add_argument('--generation-seconds',type=int,default=300,help='0 disables generation wall-clock cutoff');p.add_argument('--max-tokens',type=int,default=8192);p.add_argument('--context-window',type=int,default=32768);p.add_argument('--max-tool-calls',type=int,default=100,help='0 disables total tool-call cutoff');a=p.parse_args()
    if a.generation_seconds<0 or a.max_tokens<1 or a.context_window<a.max_tokens or a.max_tool_calls<0:p.error('Invalid generation limits')
    directory=Path(os.environ['SHELLSEM_RUN_DIR']).resolve()
    try:r=run(a.task,a.label,directory,a.generation_seconds,a.max_tokens,a.context_window,a.max_tool_calls);print(json.dumps(r),flush=True)
    except Exception as e:
        atomic_json(directory/'result.json',{'status':'infrastructure_error','error_type':type(e).__name__,'error':str(e)[:1000]});raise

if __name__=='__main__':main()
