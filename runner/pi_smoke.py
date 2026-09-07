import sys, os, json, subprocess
from pathlib import Path
from runner.config import load_config
root=Path.cwd()
import argparse
parser = argparse.ArgumentParser(description='Pi streaming preflight without tools')
parser.add_argument('--env', type=Path, default=Path('.env'))
parser.add_argument('--label', choices=['preview', 'baseline'], default='preview')
options = parser.parse_args()
c=load_config(options.env)
config=root/f'.runtime/pi-smoke-config-{options.label}'
work=root/f'.runtime/pi-smoke-work-{options.label}'
config.mkdir(exist_ok=True)
work.mkdir(exist_ok=True)
model={'id':c.model_id,'reasoning':True,'input':['text'],'contextWindow':8192,'maxTokens':1024,'compat':{'supportsStore':False,'supportsDeveloperRole':False,'supportsReasoningEffort':False,'maxTokensField':'max_tokens'}}
(config/'models.json').write_text(json.dumps({'providers':{'qwen-bench':{'baseUrl':c.base_url,'api':'openai-completions','apiKey':'$QWEN_API_KEY','models':[model]}}}))
(config/'settings.json').write_text((root/'configs/pi-settings.json').read_text())
env=os.environ.copy()
env.update(QWEN_API_KEY=c.api_key,PI_CODING_AGENT_DIR=str(config),PI_OFFLINE='1')
args=[str(root/'.runtime/pi/node_modules/.bin/pi'),'--offline','--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files','--no-tools','--no-session','--provider','qwen-bench','--model',c.model_id,'--mode','json','-p','Reply with exactly PI_OK.']
r=subprocess.run(args,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=90)
out=root/f'runs/pi-api-preflight-{options.label}'
out.mkdir(parents=True,exist_ok=True)
(out/'events.jsonl').write_text(r.stdout.replace(c.api_key,'[REDACTED]'))
(out/'stderr.log').write_text(r.stderr.replace(c.api_key,'[REDACTED]'))
print(json.dumps({'returncode':r.returncode,'events':str(out/'events.jsonl'),'stderr':r.stderr[-1500:].replace(c.api_key,'[REDACTED]')}))
for line in r.stdout.splitlines():
    try:
        event=json.loads(line)
        if event.get('type')=='message_end':
            print(json.dumps(event,ensure_ascii=False))
    except ValueError:
        pass

passed = False
for line in r.stdout.splitlines():
    try:
        event = json.loads(line)
    except ValueError:
        continue
    message = event.get('message', {})
    if event.get('type') == 'message_end' and message.get('role') == 'assistant':
        text = ''.join(item.get('text', '') for item in message.get('content', []) if item.get('type') == 'text')
        passed = message.get('stopReason') == 'stop' and text.strip() == 'PI_OK'
raise SystemExit(0 if r.returncode == 0 and passed else 1)
