"""Export an exact-byte input bundle without starting the web workbench."""
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
app=SimpleNamespace(**run_path(str(ROOT/'workbench.py')))
def browser_catalog():
    names={'agent_crash_lab.py','workbench.py','BASELINES.json','verification/native-crash-comparison.json','tools/scenario_lab.py','episode_oracle.py','token_review.py'}
    for row in app.BASELINES.values():names.update([row['task'],*row['sources'].values()])
    labels=[('upstream-failed-withdrawal','Rights lost after a failed withdrawal'),('ai-payment','An allowed agent payment'),('upstream-refund','A fully returned deposit'),('upstream-healthy','Two successful withdrawals'),('upstream-auth','An unauthorized withdrawal fails')]
    recordings=[{'id':key,'title':title,'path':'verification/token-study/'+key+'.json'} for key,title in labels]
    recordings.extend({'id':key,'title':title,'path':'verification/event-study/inputs/'+key+'.json'} for key,title in [('sdk-1-bob','Official mint event · constructed envelope'),('sdk-3-alice','Official burn event · constructed envelope'),('sdk-5-bob','Official batch transfer · constructed envelope')])
    names.update(r['path'] for r in recordings)
    captures=ROOT/'verification/rpc-study';source_files=['verification/rpc-study/EXPECTED-FROM-PUBLISHED.json']
    for request in sorted(captures.rglob('request.json')):
        source_files.extend((request.parent/file).relative_to(ROOT).as_posix() for file in ['request.json','response.json','observation.json'])
    source_files=sorted(source_files);names.update(source_files);names.add('tools/verify_token_rpc.py')
    inventory={p.removeprefix('verification/rpc-study/'):{'bytes':(ROOT/p).stat().st_size,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in source_files}
    source={'module':'tools/verify_token_rpc.py','files':source_files,'datasetSha256':hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'cases':[{'id':key,'recordingSha256':hashlib.sha256((ROOT/'verification/token-study'/(key+'.json')).read_bytes()).hexdigest()} for key in ['upstream-failed-withdrawal','ai-payment']]}
    for row in source['cases']:
        value=app.token_source_check({'recording_sha256':row['recordingSha256']})
        row['expectedResponseSha256']=hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'format':'agent-crash-lab/browser-v1','scenarios':app.CURATED,'baselines':list(app.BASELINES.values()),'tokenRecordings':recordings,'sourceCorroboration':source,'files':{n:{'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in sorted(names)}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scenario',choices=[*app.CATALOG,'browser-catalog']);p.add_argument('output',type=Path);a=p.parse_args()
    if a.scenario=='browser-catalog':b=browser_catalog()
    else:
        scenario=app.CATALOG[a.scenario]
        b=app.bundle(*app.data_for(scenario),scenario)
    a.output.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\r\n')
    print(a.output)
if __name__=='__main__':main()
