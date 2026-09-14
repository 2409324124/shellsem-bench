"""Archive completed trajectories for the private repository, excluding credentials."""
import argparse,gzip,hashlib,io,json,tarfile
from pathlib import Path
from runner.config import load_config
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'request.json','response.raw.json','first-answer.txt','capture.json','prompt.md','grade.json',
         'submission.sh','http-error.txt','events.jsonl','last-assistant.json','effective-config.json',
         'stagnation-evidence.json','process-exhaustion.txt','result.json','generation-result.json','guard.json','runner.json','collect.artifact.sh'}


def main():
    p=argparse.ArgumentParser();p.add_argument('runs',nargs='+',type=Path);a=p.parse_args()
    output=ROOT/'evidence/2026-09-14';output.mkdir(parents=True,exist_ok=True)
    secrets=[load_config(ROOT/f).api_key.encode() for f in ('.env','.env.baseline')]
    manifest_file=output/'manifest.json'
    manifest=json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    for directory in a.runs:
        directory=directory.resolve()
        guard=directory/'guard.json'
        if guard.exists() and json.loads(guard.read_text()).get('status') not in ('finished','terminated'):
            raise ValueError('Cannot archive a live run')
        capture=directory/'capture.json'
        if capture.exists() and json.loads(capture.read_text()).get('status')=='requesting':raise ValueError('Cannot archive a live API request')
        name=directory.name if directory.parent.name=='runs' else directory.parent.name+'-'+directory.name
        packed=io.BytesIO();count=0
        with gzip.GzipFile(fileobj=packed,mode='wb',mtime=0) as gz:
            with tarfile.open(fileobj=gz,mode='w') as tar:
                for f in sorted(directory.rglob('*')):
                    if not f.is_file():continue
                    rel=f.relative_to(directory)
                    selected=(len(rel.parts)==1 and f.name in ALLOWED) or rel.parts[0]=='requests' or (rel.parts[0]=='verification' and f.name in ('result.json','stdout.bin','stderr.bin'))
                    if not selected:continue
                    data=f.read_bytes()
                    if any(secret in data for secret in secrets):raise ValueError('Credential found; refusing archive')
                    info=tarfile.TarInfo(str(rel));info.size=len(data);info.mode=0o644;info.mtime=0
                    tar.addfile(info,io.BytesIO(data));count+=1
        data=packed.getvalue();filename=name+'.tar.gz';(output/filename).write_bytes(data)
        manifest[name]={'archive':filename,'sha256':hashlib.sha256(data).hexdigest(),'files':count,'compressed_bytes':len(data),'credentials_scan':'passed','source_directory':str(directory.relative_to(ROOT))}
        print(filename,len(data),flush=True)
    manifest_file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
