import sys, json, urllib.request, urllib.error
from pathlib import Path
from runner.config import load_config
from runner.probe import NoRedirect
import argparse
parser = argparse.ArgumentParser(description='Test chat and tool roundtrip')
parser.add_argument('--env', type=Path, default=Path('.env'))
args = parser.parse_args()
c=load_config(args.env)
opener=urllib.request.build_opener(NoRedirect)
def call(messages, **extra):
    body={'model':c.model_id, 'messages':messages, 'max_tokens':1024, 'stream':False, **extra}
    req=urllib.request.Request(c.base_url+'/chat/completions', data=json.dumps(body).encode(), headers={'Authorization':'Bearer '+c.api_key,'Content-Type':'application/json'})
    with opener.open(req, timeout=60) as r:
        return json.load(r)
try:
    first=call([{'role':'user','content':'Reply with exactly API_OK.'}])
    msg=first['choices'][0]['message']
    if msg.get('content', '').strip() != 'API_OK':
        raise ValueError('Unexpected chat output')
    print(json.dumps({'test':'chat','response_model':first.get('model'),'content':msg.get('content'),'finish_reason':first['choices'][0].get('finish_reason'),'usage':first.get('usage')}, ensure_ascii=False),flush=True)
    messages=[{'role':'user','content':'Call benchmark_echo with text TOOL_OK. After the tool returns, reply with its result.'}]
    tool={'type':'function','function':{'name':'benchmark_echo','description':'Returns supplied text unchanged.','parameters':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False}}}
    second=call(messages,tools=[tool],tool_choice='auto')
    reply=second['choices'][0]['message']
    calls=reply.get('tool_calls',[])
    valid=len(calls)==1 and calls[0]['function']['name']=='benchmark_echo' and json.loads(calls[0]['function']['arguments'])=={'text':'TOOL_OK'}
    print(json.dumps({'test':'tool_call','valid':valid,'finish_reason':second['choices'][0].get('finish_reason'),'usage':second.get('usage')}),flush=True)
    if not valid:
        sys.exit(1)
    if valid:
        messages.append(reply)
        messages.append({'role':'tool','tool_call_id':calls[0]['id'],'content':'TOOL_OK'})
        third=call(messages,tools=[tool])
        if third['choices'][0]['message'].get('content', '').strip() != 'TOOL_OK':
            raise ValueError('Unexpected roundtrip output')
        print(json.dumps({'test':'tool_roundtrip','content':third['choices'][0]['message'].get('content'),'usage':third.get('usage')},ensure_ascii=False),flush=True)
except urllib.error.HTTPError as exc:
    print(json.dumps({'http_status':exc.code,'error':exc.read(4096).decode(errors='replace').replace(c.api_key,'[REDACTED]')}))
    sys.exit(1)
except Exception as exc:
    print(json.dumps({'error_type':type(exc).__name__}))
    sys.exit(1)
