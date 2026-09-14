"""Save an unmodified first answer before any grading; never contact a model."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]


def capture(task,model,url,response,run_id,settings_note):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('Invalid run id')
    manifest=json.loads((ROOT/'single_shot/manifest.json').read_text())
    item=next(t for t in manifest['tasks'] if t['id']==task)
    prompt=(ROOT/'single_shot'/item['prompt']).read_bytes()
    if hashlib.sha256(prompt).hexdigest()!=item['sha256']:raise ValueError('Prompt changed after manifest creation')
    raw=Path(response).read_bytes()
    if not raw:raise ValueError('Empty response: record the failed attempt separately, not as an answer')
    dest=ROOT/'runs/single-shot'/run_id
    dest.mkdir(parents=True,exist_ok=False)
    try:
        (dest/'first-answer.txt').write_bytes(raw)
        (dest/'prompt.md').write_bytes(prompt)
        record={'task':task,'model_as_displayed':model,'conversation_url':url,
                'captured_at':datetime.now(timezone.utc).isoformat(),
                'first_answer_sha256':hashlib.sha256(raw).hexdigest(),'prompt_sha256':item['sha256'],
                'settings_evidence_note':settings_note,'capture_source':'operator-provided web transcript',
                'grading_status':'not_started','api_used':False,'pi_used':False}
        (dest/'capture.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        for p in dest.iterdir():p.chmod(0o444)
    except BaseException:
        shutil.rmtree(dest)
        raise
    return dest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=('Q1','Q2'),required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--url',required=True)
    parser.add_argument('--response',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--settings-note',required=True,help='Observed tool settings, thinking mode and first-answer provenance; do not guess')
    a=parser.parse_args()
    print(capture(a.task,a.model,a.url,a.response,a.run_id,a.settings_note))


if __name__=='__main__':main()
