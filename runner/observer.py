"""Loopback-only, read-only observer, independent of runner and guard."""
import argparse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, parse_qs
from runner.state import read_json
from runner.scoring import summarize,read_events


@lru_cache(maxsize=128)
def historical_score(directory, result_data, event_stamp):
    p=Path(directory)
    return summarize(json.loads(result_data),read_events(p/'events.jsonl'))


def score_for(p,result):
    if result.get('score'):return result['score']
    if not result:return {}
    event=p/'events.jsonl'
    return historical_score(str(p),json.dumps(result,sort_keys=True),
                            (event.stat().st_mtime_ns,event.stat().st_size) if event.exists() else None)


def snapshot(root):
    now=time.time()
    runs=[]
    for p in sorted(root.iterdir()) if root.exists() else []:
        if not p.is_dir() or not (p/'guard.json').exists(): continue
        guard=read_json(p/'guard.json'); runner=read_json(p/'runner.json')
        age=now-guard.get('heartbeat', 0)
        health='guard_stale' if guard.get('status')=='watching' and age>5 else guard.get('status')
        result=read_json(p/'result.json')
        if not result and guard.get('status') in ('finished','terminated'):
            result={'status':'runner_interrupted','generation_failure':guard.get('reason') or 'missing_result'}
        score=score_for(p,result)
        runs.append({'score':score,'id':p.name, 'health':health, 'guard':guard, 'runner':runner,
            'runner_heartbeat_age':now-runner.get('heartbeat',now),
            'activity_age':now-runner.get('last_activity',now), 'result':result, 'verification':read_json(p/'verifier-progress.json')})
    suite=read_json(root/'suite.json')
    if suite.get('status')=='running' and now-suite.get('heartbeat',0)>5:suite['status']='scheduler_stale'
    return {'server_time':now, 'suite':suite, 'runs':runs}

HTML=r'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ShellSem Live</title>
<style>body{font:15px system-ui;background:#10151c;color:#e0e7f0;margin:24px;max-width:1400px}h1{font-size:24px}h2{font-size:18px}select,button{font:inherit;padding:8px;background:#233041;color:inherit;border:1px solid #506078}pre{background:#1c2531;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:48vh;overflow:auto}table{border-collapse:collapse;width:100%;margin:16px 0}td,th{text-align:left;border-bottom:1px solid #344254;padding:8px}tr{cursor:pointer}.bad{color:#ffad90}.ok{color:#84dec1}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}.metric{padding:12px;background:#1c2531}.value{display:block;font-size:23px;margin-top:5px}small{color:#b3c1d2}</style>
<h1>ShellSem · 实时运行状态</h1><p>关闭思考 · Docker 网络开启 · 提交正确性与生成过程分别记录</p><p id="connection">连接中</p><p id="suite"></p>
<table><thead><tr><th>运行</th><th>阶段 / 结果</th><th>提交评分</th><th>生成过程</th><th>重试</th><th>总墙钟</th><th>活动距今</th><th>健康状态</th></tr></thead><tbody id="matrix"></tbody></table>
<select id="runs"></select><div class="grid" id="metrics"></div><h2>生成异常与重试记录</h2><pre id="anomalies"></pre><h2>正在生成的增量</h2><pre id="stream"></pre><h2>最新模型行为</h2><pre id="live"></pre>
<details><summary>完整状态与进程资源</summary><pre id="status"></pre></details><details><summary>原始事件（最近 128 KiB）</summary><pre id="events"></pre></details>
<script>
const $=s=>document.querySelector(s),fmt=n=>Number.isFinite(n)?n.toFixed(1)+' 秒':'—';let selected='';
const anomalyLabel={api_timeout:'API 请求超时',api_connect_timeout:'连接建立超时',api_request_aborted:'请求被取消或触达期限',api_connection_error:'API 连接失败',api_rate_limit:'API 限流',api_server_error:'API 服务异常',api_auth_error:'鉴权失败',api_quota_error:'额度不足',output_truncated:'输出被截断',tool_budget_exceeded:'工具调用预算耗尽',generation_time_limit:'生成时间预算耗尽',event_log_limit:'事件日志上限',retry_exhausted:'重试耗尽',retry_cancelled:'重试取消',tool_error:'工具报错',shell_nonzero_exit:'Shell 非零退出'};
const processLabel={completed:'正常结束',completed_with_anomalies:'结束，有异常',recovered:'重试恢复',failed:'生成失败',unknown:'过程证据不足'};
const phase={generating:'模型生成',verifying:'隐藏验证',case_setup:'准备 case',starting:'启动',finished:'结束'};
async function tick(){try{let s=await fetch('/api/status',{cache:'no-store'}).then(r=>r.json());$('#suite').textContent=s.suite.total?'Smoke '+s.suite.completed.length+'/'+s.suite.total+' 完成 · '+s.suite.active.length+' 运行中 · '+s.suite.status+' · 并发度 '+(s.suite.concurrency??'旧配置 2'):'';
let menu=$('#runs'),old=menu.value;menu.replaceChildren(...s.runs.map(r=>{let o=document.createElement('option');o.value=r.id;o.textContent=r.id+' · '+(r.result.status||r.health);return o}));menu.value=s.runs.some(r=>r.id===old)?old:(s.runs.findLast(r=>r.guard.status==='watching')?.id||s.runs.at(-1)?.id||'');
$('#matrix').replaceChildren(...s.runs.map(r=>{let tr=document.createElement('tr');let sub=r.score?.submission,gen=r.score?.generation||r.runner.generation;let vals=[r.id,r.result.status||phase[r.runner.phase]||r.runner.phase,sub?.total?sub.passed+'/'+sub.total+' '+sub.status:'未验证',gen?(r.result.status?(processLabel[gen.status]||gen.status):'进行中')+(gen.failure?' · '+gen.failure:''):'—',gen?.retry_count??0,fmt(r.guard.elapsed),r.guard.status==='watching'?fmt(r.activity_age):'已结束',r.health];for(let val of vals){let td=document.createElement('td');td.textContent=val;tr.append(td)}tr.onclick=()=>menu.value=r.id;return tr}));
let r=s.runs.find(r=>r.id===menu.value);$('#status').textContent=JSON.stringify(r||s,null,2);$('#metrics').replaceChildren();if(r){let g=r.score?.generation||r.runner.generation||{};let notes=['提交状态：'+(r.result.submission_reason||r.score?.submission?.status||'尚未验证'),'生成过程：'+(r.result.status?(processLabel[g.status]||g.status||'—'):'进行中'),'异常：'+((g.anomalies||[]).map(a=>anomalyLabel[a]||a).join('、')||'尚未记录'),'工具报错 '+(g.tool_errors??0)+' 次；Shell 非零退出 '+(g.shell_nonzero_exits??'未记录')+' 次'];for(let [i,a] of (g.retries||[]).entries())notes.push('重试记录 '+(i+1)+'（本轮第 '+a.attempt+' 次）：等待 '+a.delayMs/1000+' 秒；'+(a.errorMessage||'').slice(0,180));for(let e of g.transport_errors||[])notes.push('网络诊断：'+e.elapsed_ms+' ms；'+(e.error?.cause?.code||e.error?.name||'')+'；'+(e.error?.cause?.message||e.error?.message||''));if(r.runner.retry)notes.push('当前退避，距下一次尝试约 '+Math.max(0,Math.ceil(r.runner.retry.next_attempt_at-s.server_time))+' 秒');if(r.result.artifact_origin==='interrupted')notes.push('提交来自中断的生成过程，通过用例不代表完整运行成功。');$('#anomalies').textContent=notes.join('\n');let vals=[['生成耗时',fmt(r.result.generation_seconds??(r.runner.phase==='generating'?r.runner.elapsed:undefined))],['生成剩余',fmt(r.runner.remaining_seconds)],['验证耗时',fmt(r.result.verification_seconds)],['工具调用',r.result.tool_calls??r.runner.tool_calls??'—'],['已完成回复 reasoning tokens',r.result.usage?.reasoning??r.runner.usage?.reasoning??'—'],['Runner 心跳距今',fmt(r.runner_heartbeat_age)]];for(let [k,v] of vals){let d=document.createElement('div');d.className='metric';d.textContent=k;let b=document.createElement('span');b.className='value';b.textContent=v;d.append(b);$('#metrics').append(d)}
let raw=await fetch('/api/events?run='+encodeURIComponent(r.id)).then(r=>r.text());$('#events').textContent=raw;let lines=[],deltas=[];for(let line of raw.split('\n')){try{let e=JSON.parse(line);if(['auto_retry_start','auto_retry_end','api_transport_error'].includes(e.type))lines.push('API / 重试：'+JSON.stringify(e));if(e.type==='message_update'&&typeof e.delta==='string')deltas.push(e.delta);if(e.type==='tool_execution_start')lines.push('▶ '+e.toolName+' '+JSON.stringify(e.args));if(e.type==='tool_execution_end')lines.push((e.isError?'✗ ':'✓ ')+e.toolName+' '+JSON.stringify(e.result));if(e.type==='message_end'&&e.message?.role==='assistant'){let t=e.message.content.filter(x=>x.type==='text').map(x=>x.text).join('');if(t)lines.push('模型：'+t)}}catch{}}$('#stream').textContent=deltas.join('').slice(-6000);$('#live').textContent=lines.slice(-18).join('\n\n')||'正在接收模型流；展开原始事件可查看增量。'}
$('#connection').textContent='观察服务在线 · '+new Date().toLocaleTimeString();$('#connection').className='ok';}catch(e){$('#connection').textContent='观察接口不可达：'+e;$('#connection').className='bad'}finally{setTimeout(tick,1000)}}tick();
</script></html>'''


def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path('runs')); p.add_argument('--port',type=int,default=8765); args=p.parse_args()
    root=args.root.resolve()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url=urlsplit(self.path)
            if url.path=='/': data=HTML.encode(); mime='text/html; charset=utf-8'
            elif url.path=='/api/status': data=json.dumps(snapshot(root),ensure_ascii=False).encode(); mime='application/json'
            elif url.path=='/api/events':
                name=parse_qs(url.query).get('run',[''])[0]
                if not re.fullmatch(r'[A-Za-z0-9_-]+',name): self.send_error(400); return
                path=root/name/'events.jsonl'
                try:
                    with path.open('rb') as f:
                        f.seek(0,2); size=f.tell(); f.seek(max(0,size-131072)); data=f.read(131072)
                except OSError: data=b''
                mime='text/plain; charset=utf-8'
            else: self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type',mime); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data)
        def log_message(self,*args): pass
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__': main()
