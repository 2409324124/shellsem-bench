"""Evaluate already-captured first responses against exact-version Bash output."""
import hashlib,json,os,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASH=ROOT/'.runtime/bash-5.2.37/bin/bash'


def main(directories=None):
    out=ROOT/'runs/single-shot/2026-09-14-first'
    for label in ('preview','baseline'):
        assert (out/f'{label}-Q1/first-answer.txt').exists(),'Capture first, grade second'
    text=(ROOT/'single_shot/prompts/Q1.md').read_text()
    script=re.search(r'```bash\n(.*?)```',text,re.S).group(1)
    expected={}
    for variant in ('A','B'):
        code=script if variant=='A' else script.replace('shopt -u lastpipe inherit_errexit','shopt -u inherit_errexit\nshopt -s lastpipe',1)
        results=[]
        for _ in range(50):
            r=subprocess.run([str(BASH),'--noprofile','--norc','-c',code],env={'PATH':'/usr/bin:/bin','LC_ALL':'C'},capture_output=True,timeout=5)
            results.append({'stdout':r.stdout.decode(),'stderr':r.stderr.decode(),'exit_code':r.returncode})
        assert all(x==results[0] for x in results),'Non-deterministic oracle'
        expected[variant]=results[0]
    (out/'q1-expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n')
    for d in (list(map(Path,directories)) if directories else [out/f'{label}-Q1' for label in ('preview','baseline')]):
        label=d.name;raw=(d/'first-answer.txt').read_text()
        answers=[]
        for block in re.findall(r'```(?:json)?\s*\n(.*?)```',raw,re.S):
            try:
                value=json.loads(block)
                if isinstance(value,dict) and 'A' in value and 'B' in value:answers.append(value)
            except ValueError:pass
        if not answers:
            try:answers=[json.JSONDecoder().raw_decode(raw.lstrip())[0]]
            except ValueError:pass
        comparisons=[]
        for answer in answers:
            comparisons.append({v:{k:answer.get(v,{}).get(k)==expected[v][k] for k in ('stdout','stderr','exit_code')} for v in ('A','B')})
        grade={'oracle_version':'5.2.37','oracle_repetitions_per_variant':50,
               'first_answer_sha256':hashlib.sha256((d/'first-answer.txt').read_bytes()).hexdigest(),
               'json_objects_in_first_response':len(answers),'comparisons_in_order':comparisons,
               'fully_correct_any_object':any(all(all(fields.values()) for fields in pair.values()) for pair in comparisons),
               'format_starts_with_json':raw.lstrip().startswith('{'),
               'explanation_review':'manual; self-corrections inside first response retained, not separate attempts'}
        (d/'grade.json').write_text(json.dumps(grade,ensure_ascii=False,indent=2)+'\n')
        print(label,json.dumps(grade,ensure_ascii=False))
    print('EXPECTED',json.dumps(expected,ensure_ascii=False))

if __name__=='__main__':
    import sys
    main(sys.argv[1:])
