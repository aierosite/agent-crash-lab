"""Replay the saved same-author actual browser import study, offline."""
from pathlib import Path
from hashlib import sha256
import json,runpy
ROOT=Path(__file__).resolve().parents[1]
FINGERPRINTS=['token_policy.py','token_review.py','web/policy-contract.js','web/policy.js','web/token-events.js']

def inputs():
 api=runpy.run_path(str(ROOT/'token_policy.py'));pack=api['pack'];out={};data=ROOT/'verification/token-policy'
 for c in json.loads((data/'reference.json').read_bytes())['cases']:
  out[c['id']]=pack({'format':'agent-crash-lab/token-policy-bundle-v1','task_utf8':(ROOT/c['task']).read_bytes().decode(),'evidence_utf8':(ROOT/c['evidence']).read_bytes().decode()})
 for folder in ['encoding-controls','interface-controls','boundary-controls','wire-controls','empty-controls']:
  for c in json.loads((data/folder/'reference.json').read_bytes())['cases']:
   if 'bundle' in c:raw=(ROOT/c['bundle']).read_bytes()
   else:
    base=data/folder/c['id'];raw=pack({'format':'agent-crash-lab/token-policy-bundle-v1','task_utf8':(base/'task.json').read_bytes().decode(),'evidence_utf8':(base/'evidence.json').read_bytes().decode()})
   assert c['id'] not in out;out[c['id']]=raw
 for c in json.loads((ROOT/'web/catalog.json').read_bytes())['tokenPolicy']['cases']:
  if c['id'] not in out:out[c['id']]=pack({'format':'agent-crash-lab/token-policy-bundle-v1','task_utf8':(ROOT/c['task']).read_bytes().decode(),'evidence_utf8':(ROOT/c['evidence']).read_bytes().decode()})
 out.update({'invalid-json':b'{bad','empty-bundle':b'','oversize':b' '*(2*1024*1024+1),'duplicate-field':b'{"format":1,"format":2}'})
 return out

def replay(record,source_root,raws):
 api=runpy.run_path(str(source_root/'token_policy.py'));source={name:sha256((source_root/name).read_bytes()).hexdigest() for name in FINGERPRINTS};assert record['sourceFingerprints']==source;assert record['mode']=='actual-browser-python-webassembly-ui';assert record['independentBlindEvaluation'] is False;seen=set();reports=rejections=0
 for row in record['rows']:
  cid=row['id'];assert cid in raws and cid not in seen;seen.add(cid);raw=raws[cid];assert row['inputSha256']==sha256(raw).hexdigest();expected=error=None
  try:expected=api['assess_bundle'](raw)
  except ValueError as ex:error=ex
  if error is None:assert row['report']==expected and row['resultsVisible'] is True and row['error'] is None;reports+=1
  else:assert row['report'] is None and row['resultsVisible'] is False and type(row['error']) is str and len(row['error'])>0;rejections+=1
 assert seen==set(raws)
 return {'format':'agent-crash-lab/policy-browser-replay-v1','actualUiInputs':len(seen),'completeReportsMatched':reports,'rejectedInputsClearedPriorResult':rejections,'sourceFingerprints':source,'newModelCalls':0,'newTransactions':0,'networkRequests':0,'independentBlindEvaluation':False,'meaning':'Offline equality replay of same-author observed browser imports and source fingerprints. This does not launch a browser or independently grade financial correctness.'}

def verify():
 raws=inputs();record=json.loads((ROOT/'verification/token-policy/browser-verified.json').read_bytes());recorded=[r['id'] for r in record['rows']]
 assert len(recorded)==98 and len(set(recorded))==98
 result=replay(record,ROOT,{cid:raws[cid] for cid in recorded})
 billing=json.loads((ROOT/'verification/billing-study/browser-inputs.json').read_bytes());added=[r['id'] for r in billing['rows']]
 assert len(added)==4 and len(set(added))==4 and not set(added)&set(recorded)
 assert set(added)|set(recorded)==set(raws)
 result['billingBrowserStudy']=replay(billing,ROOT,{cid:raws[cid] for cid in added})
 result['allCurrentInputsCovered']=len(raws)
 history=ROOT/'evidence/token-policy-study/browser-v013';old=json.loads((history/'browser-verified.json').read_bytes());ids=[r['id'] for r in old['rows']]
 assert len(ids)==91 and len(set(ids))==91
 result['historicalBrowserStudy']=replay(old,history,{cid:raws[cid] for cid in ids})
 assert result['historicalBrowserStudy']['completeReportsMatched']==76 and result['historicalBrowserStudy']['rejectedInputsClearedPriorResult']==15
 return result

if __name__=='__main__':print(json.dumps(verify()))
