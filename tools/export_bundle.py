"""Export an exact-byte input bundle without starting the web workbench."""
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
app=SimpleNamespace(**run_path(str(ROOT/'workbench.py')))
def browser_catalog():
    names={'agent_crash_lab.py','workbench.py','BASELINES.json','verification/native-crash-comparison.json','tools/scenario_lab.py','episode_oracle.py','token_review.py','token_policy.py'}
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
    policy_cases=[{'id':key,'title':title,'kind':'observed-historical' if key in ['refunded-deposit','accepted-deposit'] else 'synthetic','task':'verification/token-policy/inputs/'+key+'/task.json','evidence':'verification/token-policy/inputs/'+key+'/evidence.json'} for key,title in [
        ('allowed-split-payments','One order, two allowed payments'),('repeated-payment-breaches-cap','A retry exceeds the order limit'),('independent-equal-price-intents','Same price, separate orders'),('sender-deleted-burn','A burned refund is not delivery'),('reported-used-is-not-delivered','Resolver used does not mean delivered'),('missing-causal-descendant-100','A missing receipt prevents settlement certainty'),('hook-returned-promise-supported','Receiver returns another promise'),('refunded-deposit','Historical testnet · deposit returned'),('accepted-deposit','Historical testnet · deposit accepted')]]
    policy_cases.extend({'id':key,'title':title,'kind':'synthetic','task':'verification/token-policy/inputs/'+key+'/task.json','evidence':'verification/token-policy/inputs/'+key+'/evidence.json'} for key,title in [('sdk-mock-accepted','Rust SDK mock · accepted payment'),('sdk-mock-burn','Rust SDK mock · refund burn')])
    policy_cases.extend({'id':key,'title':title,'kind':'synthetic','task':'verification/token-policy/inputs/'+key+'/task.json','evidence':'verification/token-policy/inputs/'+key+'/evidence.json'} for key,title in [('model-loop-repeated-payment','Qwen + SDK mock · repeated payment'),('model-loop-premature-finish','Qwen + SDK mock · unfinished work'),('model-loop-no-payments','Qwen + SDK mock · no payment records')])
    policy_cases.extend({'id':r['id'],'title':r['title'],'kind':'synthetic','task':'verification/token-policy/inputs/'+r['id']+'/task.json','evidence':'verification/token-policy/inputs/'+r['id']+'/evidence.json'} for r in json.loads((ROOT/'verification/billing-study/reference.json').read_bytes())['cases'])
    names.update(p for c in policy_cases for p in [c['task'],c['evidence']]);policy={'module':'token_policy.py','profile':'near-nep141-sdk-receipts/v1','cases':policy_cases}
    agents=json.loads((ROOT/'verification/exposure-study/catalog.json').read_bytes())
    names.update(agents['files'])
    return {'format':'agent-crash-lab/browser-v1','scenarios':app.CURATED,'baselines':list(app.BASELINES.values()),'tokenRecordings':recordings,'sourceCorroboration':source,'tokenPolicy':policy,'agentRuns':agents,'files':{n:{'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in sorted(names)}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scenario',choices=[*app.CATALOG,'browser-catalog']);p.add_argument('output',type=Path);a=p.parse_args()
    if a.scenario=='browser-catalog':b=browser_catalog()
    else:
        scenario=app.CATALOG[a.scenario]
        b=app.bundle(*app.data_for(scenario),scenario)
    a.output.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\r\n')
    print(a.output)
if __name__=='__main__':main()
