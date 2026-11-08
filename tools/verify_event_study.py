"""Replay the source-informed NEP-300 event conformance study without networking."""
from pathlib import Path
from hashlib import sha256
import json,runpy,sys
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'verification/event-study'
FIELDS=['kind','old_owner_id','new_owner_id','amount','data_index']

def projection(report):
 s=report['steps'][0];out={k:s[k] for k in ['gross_in','gross_out','event_net','conclusion']}
 out['events']=[[e[k] for k in FIELDS] for e in s['events']];return out

def verify():
 registration=json.loads((DATA/'REGISTRATION.json').read_bytes());reference=json.loads((DATA/'reference.json').read_bytes())
 assert sha256((DATA/'reference.json').read_bytes()).hexdigest()==registration['referenceSha256']
 for name,digest in registration['inputHashes'].items():assert sha256((DATA/'inputs'/name).read_bytes()).hexdigest()==digest,name
 frozen=DATA/'frozen-v012-token_review.py.txt';assert sha256(frozen.read_bytes()).hexdigest()==registration['frozenAssessorSha256']
 assert sha256((DATA/'frozen-v012-token.js.txt').read_bytes()).hexdigest()==registration['frozenClientSha256']
 initial=runpy.run_path(str(frozen))['review'];api=runpy.run_path(str(ROOT/'token_review.py'));review=api['review'];old_matches=0;rows=[]
 for case in reference['cases']:
  cid=case['id'];raw=(DATA/'inputs'/(cid+'.json')).read_bytes();old=initial(raw)
  assert old==json.loads((DATA/'initial'/(cid+'.json')).read_bytes()),cid
  old_matches+=projection(old)==case['expected'];new=review(raw);assert projection(new)==case['expected'],cid
  expected_transfer=sum(int(e[3]) for e in case['expected']['events'] if e[0]=='ft_transfer' and e[1]==new['vault'] and e[2]!=new['vault'])
  assert new['steps'][0]['transfer_out']==str(expected_transfer),cid
  rows.append({'id':cid,'inputSha256':sha256(raw).hexdigest(),'sourceVector':case['sourceVector'],'currentProjectionMatches':True,'transfersOut':str(expected_transfer)})
 assert old_matches==8 and len(rows)==19
 for cid in reference['boundaryInputs']:
  raw=(DATA/'inputs'/(cid+'.json')).read_bytes();assert initial(raw)==json.loads((DATA/'initial'/(cid+'.json')).read_bytes())
 # Source mutants change interpretation, not input hashes. They must disagree
 # with the declared literal event facts rather than merely change source hashes.
 source=(ROOT/'token_review.py').read_text('utf-8');mutants={
  'mint-owner-alias':("item.get('owner_id') if kind=='ft_mint' else item.get('new_owner_id')","item.get('new_owner_id')"),
  'burn-owner-alias':("item.get('owner_id') if kind=='ft_burn' else item.get('old_owner_id')","item.get('old_owner_id')"),
  'drop-batch-tail':('for di,item in enumerate(data):','for di,item in enumerate(data[:1]):'),
 }
 caught=[]
 for name,(before,after) in mutants.items():
  assert source.count(before)==1,name;ns={'__file__':str(ROOT/'token_review.py'),'__name__':'event_mutant'};exec(compile(source.replace(before,after),name,'exec'),ns)
  disagreements=[c['id'] for c in reference['cases'] if projection(ns['review']((DATA/'inputs'/(c['id']+'.json')).read_bytes()))!=c['expected']];assert disagreements,name;caught.append({'id':name,'disagreements':disagreements})
 return {'format':'agent-crash-lab/event-conformance-results-v1','externallyAuthoredSerializedVectors':8,'derivedOfficialOwnerContexts':15,'constructedAliasControls':4,'initialMatched':old_matches,'currentMatched':len(rows),'total':len(rows),'originalReportsReproduced':21,'semanticMutantsCaught':caught,'cases':rows,'assessorSha256':sha256((ROOT/'token_review.py').read_bytes()).hexdigest(),'referenceSha256':registration['referenceSha256'],'newModelCalls':0,'newTransactions':0,'independentBlindEvaluation':False,'meaning':'Verbatim official event serializations with original synthetic receipt/state envelopes and same-author direction reference. Source-informed conformance checks, not independent end-to-end safety accuracy.'}

def main():
 try:print(json.dumps(verify()));return 0
 except (AssertionError,ValueError,KeyError,TypeError,OSError) as e:print(json.dumps({'verified':False,'error':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
