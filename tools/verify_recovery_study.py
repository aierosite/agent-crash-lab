"""Replay original and corrected same-author recovery studies without a network or chain."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import argparse,json

def pack(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def load(raw,filename):
 namespace={'__name__':'recovery_replay','__file__':str(filename)}
 exec(compile(raw,str(filename),'exec'),namespace)
 return namespace
def gate(report):
 if report['invocation']['status']!='assessed':return 2
 rows=report['constraints']
 if any(row['status']=='breached' for row in rows):return 1
 return 0 if rows and all(row['status']=='within' for row in rows) and report['coverage']['financial_scope_complete'] else 2
def projection(report,expected):
 if report['invocation']['status']!='assessed':return {'invocation':report['invocation']['status'],'code':report['invocation'].get('code')}
 rows={row['id']:row for row in report['constraints']};facts={row['id']:row for row in report['native_facts']};result={}
 for cid,fields in expected['constraints'].items():
  if cid.endswith('-projection'):
   parents=rows[cid.removesuffix('-projection')+'-recovery-full']['parents']
   forbidden={fid for parent in parents for fid in parent['forbidden_refund_facts']}
   result[cid]={'returned':str(sum(int(p['successful_allowed_yocto']) for p in parents)),
                'diverted':str(sum(int(facts[fid]['committed_yocto']) for fid in forbidden))}
  else:result[cid]={key:rows[cid][key] for key in fields}
 return {'constraints':result,'gate':gate(report)}

def verify(study,core_path):
 frozen=(study/'frozen-core.py.txt').read_bytes();current=core_path.read_bytes()
 assert current==frozen,'Engine changed: explicit reassessment is required; do not rewrite archived reports.'
 core=load(frozen,study/'frozen-core.py.txt');core_hash=sha256(frozen).hexdigest()
 stages=[('initial','registration.json','sources-before-amendment','bundles',None),
         ('amended','registration-amended.json','sources-before-reference-correction','bundles-amended','initial-evaluation'),
         ('corrected','reference-correction.json',None,'bundles-corrected','corrected-evaluation')]
 stages_result=[];current_reports={}
 for label,filename,snapshot,folder,evaluation in stages:
  registration=json.loads((study/filename).read_bytes());assert registration['baseCoreSha256']==core_hash
  sources={}
  for name,digest in registration['sourceHashes'].items():
   path=study/snapshot/name if snapshot and name in ['recovery_builder.py','recovery_reference.py'] else study/name
   if not path.exists():path=Path(str(path)+'.txt')
   raw=path.read_bytes();assert sha256(raw).hexdigest()==digest,name;sources[name]=raw
  # Reconstruct with the original relative archive location, using exact sealed source bytes.
  builder=load(sources['recovery_builder.py'],study/'recovery_builder.py')
  reference=load(sources['recovery_reference.py'],study/'recovery_reference.py')
  assert reference['archive_controls']()==registration['referenceControls']
  recorded=json.loads((study/evaluation/'results.json').read_bytes()) if evaluation else None
  original_rows={row['case']:row for row in recorded['engines'][0]['cases']} if recorded else {}
  disagreements=0;checks=[]
  for plan in registration['plans']:
   name=plan['id'];file=folder+'/'+name+'.json';raw=(study/file).read_bytes()
   assert sha256(raw).hexdigest()==registration['bundles'][file]
   assert builder['pack'](builder['build'](plan))==raw,(label,name,'reconstruction')
   expected=reference['reference'](plan);assert expected==registration['expected'][name],(label,name,'reference')
   if not evaluation:continue
   bundle=json.loads(raw);report=core['assess'](bundle['task_utf8'].encode(),{key:text.encode() for key,text in bundle['sources_utf8'].items()})
   assert report['invocation']['status']=='assessed'
   actual=projection(report,expected);digest=sha256(core['pack'](report)).hexdigest()
   assert digest==original_rows[name]['reportSha256'],(label,name,'full report digest')
   assert original_rows[name]['actual']==actual and original_rows[name]['expected']==expected
   assert (actual==expected)==original_rows[name]['matches']
   disagreements+=actual!=expected;checks.append({'case':name,'reportSha256':digest,'agreesWithReference':actual==expected,'gate':actual['gate']})
   if label=='corrected':current_reports[name]=report
  if evaluation:
   assert disagreements==recorded['summary']['original']['disagreements']
   mutation_checks=[]
   seals=json.loads((study/evaluation/'mutants-before-evaluation.json').read_bytes())['sources']
   for name,digest in seals.items():
    raw=(study/evaluation/'mutants'/(name+'.py.txt')).read_bytes();assert sha256(raw).hexdigest()==digest
    mutant=load(raw,study/evaluation/'mutants'/(name+'.py.txt'));count=0
    recorded_engine=next(row for row in recorded['engines'] if row['engine']==name)
    for plan in registration['plans']:
     bundle=json.loads((study/folder/(plan['id']+'.json')).read_bytes());expected=registration['expected'][plan['id']]
     report=mutant['assess'](bundle['task_utf8'].encode(),{key:text.encode() for key,text in bundle['sources_utf8'].items()})
     old_row=next(row for row in recorded_engine['cases'] if row['case']==plan['id'])
     actual=projection(report,expected)
     assert sha256(mutant['pack'](report)).hexdigest()==old_row['reportSha256']
     assert actual==old_row['actual'];count+=actual!=expected
    assert count==recorded_engine['disagreements'] and count>0
    mutation_checks.append({'mutation':name,'reproducedDisagreements':count})
  else:mutation_checks=[]
  stages_result.append({'stage':label,'bundlesReconstructed':len(registration['plans']),
   'actualEngineReportsChecked':checks,'originalDisagreements':disagreements if evaluation else None,'mutations':mutation_checks})
 # Direct source-marker role expectations supplement, rather than replace, the sealed plan reference.
 observation=json.loads((study/'archive/observation.json').read_bytes());expected_roles={}
 for index in [8,17]:
  for body in observation['rpcObservations'][index]['response']['result']['receipts']:
   if body['predecessor_id']=='system':
    signer=body['receipt']['Action']['signer_id']
    expected_roles[body['receipt_id']]='principal_refund' if signer=='system' else 'gas_return'
 facts={fact['receipt_id']:fact for fact in current_reports['original-both']['native_facts']}
 assert expected_roles and all(facts[rid]['role']==role for rid,role in expected_roles.items())
 assert sum(role=='principal_refund' for role in expected_roles.values())==4
 return {'format':'agent-crash-lab/recovery-replay-v1','atUtc':datetime.now(timezone.utc).isoformat(),
  'verified':True,'coreSha256':core_hash,'stages':stages_result,'sourceBoundSystemRoleChecks':len(expected_roles),
  'rawAccountDeltaChecks':4,'originalReferenceErrorReproduced':True,'correctedReferenceDisagreements':0,
  'originalNativeConditions':2,'originalSignedRootAttempts':2,'originalChains':1,'newNativeExecutions':0,'newInferenceCalls':0,
  'scope':'Same-author archive/projection replay. Separate original reference implementation; not independent authorship, fresh native execution, external blind accuracy or consensus authentication.'}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--core',type=Path,default=Path(__file__).resolve().parents[1]/'agent_crash_lab.py')
 parser.add_argument('--output',type=Path);args=parser.parse_args()
 if args.output:assert not args.output.exists(),'Choose a new evidence output path.'
 result=verify(Path(__file__).resolve().parents[1]/'evidence/recovery-study',args.core)
 if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({key:result[key] for key in ['verified','sourceBoundSystemRoleChecks','rawAccountDeltaChecks','originalReferenceErrorReproduced','correctedReferenceDisagreements']}))
if __name__=='__main__':main()
