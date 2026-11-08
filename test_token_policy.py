"""Portable source-informed payment-policy checks; no fresh chain/model execution."""
from pathlib import Path
from hashlib import sha256
import copy,json,runpy,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'verification/token-policy';HISTORY=ROOT/'evidence/token-policy-study'
api=runpy.run_path(str(ROOT/'token_policy.py'));assess=api['assess'];pack=api['pack']
REFERENCE=json.loads((DATA/'reference.json').read_bytes());CASES={c['id']:c for c in REFERENCE['cases']}

def inputs(cid):
 c=CASES[cid];return (ROOT/c['task']).read_bytes(),(ROOT/c['evidence']).read_bytes()

def check(fn,c):
 tr,er=inputs(c['id']);expected=c['expected'];error=report=None
 try:report=fn(tr,er)
 except ValueError as ex:error=ex
 if expected.get('error'):return error is not None
 if 'structuredErrorOrGate' in expected:
  return error is not None or report['gate']==expected['structuredErrorOrGate'] and ('grossKnown' not in expected or report['intents'][0]['gross_known']==expected['grossKnown'])
 if error is not None or report['gate']!=expected['gate']:return False
 if expected.get('settlement') is not None and any(p['settlement_status']!=expected['settlement'] for p in report['payments']):return False
 if expected.get('settledKnownMinimum') is not None and report['intents'][0]['settled_known_min']!=expected['settledKnownMinimum']:return False
 return 'quantities' not in expected or {k:report['payments'][0][k] for k in expected['quantities']}==expected['quantities']

class PaymentPolicy(unittest.TestCase):
 def test_observed_browser_imports_replay_against_current_bytes(self):
  result=runpy.run_path(str(ROOT/'tools/verify_policy_browser.py'))['verify']();self.assertEqual(result['actualUiInputs'],91);self.assertEqual(result['completeReportsMatched'],76);self.assertEqual(result['rejectedInputsClearedPriorResult'],15)
 def test_malformed_rpc_errors_cannot_be_silently_ignored(self):
  plan=json.loads((DATA/'wire-controls/reference.json').read_bytes());old=runpy.run_path(str(HISTORY/'wire/token_policy.py.txt'))['assess']
  for c in plan['cases']:
   raw=(ROOT/c['bundle']).read_bytes();self.assertEqual(sha256(raw).hexdigest(),c['sha256']);b=json.loads(raw);tr=b['task_utf8'].encode();er=b['evidence_utf8'].encode();original=old(tr,er);self.assertEqual(original,json.loads((HISTORY/'wire'/(c['id']+'-original.json')).read_bytes()));self.assertEqual(original['gate'],0)
   with self.subTest(case=c['id']):self.assertEqual(assess(tr,er)['gate'],2)
 def test_null_fields_and_rpc_identity_boundaries(self):
  plan=json.loads((DATA/'boundary-controls/reference.json').read_bytes());old=runpy.run_path(str(HISTORY/'boundary/token_policy.py.txt'))['assess']
  for c in plan['cases']:
   raw=(ROOT/c['bundle']).read_bytes();self.assertEqual(sha256(raw).hexdigest(),c['sha256']);b=json.loads(raw);tr=b['task_utf8'].encode();er=b['evidence_utf8'].encode();original=old(tr,er);self.assertEqual(original,json.loads((HISTORY/'boundary'/(c['id']+'-original.json')).read_bytes()));self.assertEqual(original['gate'],c['originalGate'])
   with self.subTest(case=c['id']):self.assertEqual(assess(tr,er)['gate'],c['expectedGate'])
 def test_exact_integer_and_interface_controls(self):
  plan=json.loads((DATA/'interface-controls/reference.json').read_bytes())
  for c in plan['cases']:
   raw=(ROOT/c['bundle']).read_bytes();self.assertEqual(sha256(raw).hexdigest(),c['sha256']);r=api['assess_bundle'](raw)
   with self.subTest(case=c['id']):self.assertEqual(r['gate'],c['expectedGate'])
   if c['id']=='prototype-id-text':self.assertEqual(r['intents'][0]['intent'],'__proto__')
 def test_sdk_output_uses_utf8_not_encoding_autodetection(self):
  data=DATA/'encoding-controls';plan=json.loads((data/'reference.json').read_bytes());frozen=runpy.run_path(str(HISTORY/'encoding/token_policy.py.txt'))['assess']
  for c in plan['cases']:
   folder=data/c['id'];tr=(folder/'task.json').read_bytes();er=(folder/'evidence.json').read_bytes();self.assertEqual(sha256(tr).hexdigest(),c['taskSha256']);self.assertEqual(sha256(er).hexdigest(),c['evidenceSha256']);old=frozen(tr,er);self.assertEqual(old,json.loads((HISTORY/'encoding'/(c['id']+'.json')).read_bytes()));self.assertEqual(old['gate'],c['originalGate']);r=assess(tr,er)
   with self.subTest(case=c['id']):
    self.assertEqual(r['gate'],c['expectedGate']);self.assertEqual(r['payments'][0]['settlement_status'],c['expectedSettlement'])
    if c['expectedUnused'] is not None:self.assertEqual(r['payments'][0]['callback']['unused_limit'],c['expectedUnused'])
 def test_registered_and_labeled_controls(self):
  self.assertEqual(len(CASES),69)
  for c in REFERENCE['cases']:
   with self.subTest(case=c['id']):self.assertTrue(check(assess,c))
 def test_exact_input_fingerprints(self):
  for c in REFERENCE['cases']:
   tr,er=inputs(c['id']);self.assertEqual(sha256(tr).hexdigest(),c['taskSha256']);self.assertEqual(sha256(er).hexdigest(),c['evidenceSha256'])
 def test_preserved_prototype_reports(self):
  frozen=runpy.run_path(str(HISTORY/'prototype/token_policy_lab.py.txt'))['assess']
  for c in REFERENCE['cases']:
   if c['group']=='registered-source-informed':
    with self.subTest(case=c['id']):self.assertEqual(frozen(*inputs(c['id'])),json.loads((HISTORY/'prototype-reports'/(c['id']+'.json')).read_bytes()))
 def test_initial_integration_failures_reproduced(self):
  frozen=runpy.run_path(str(HISTORY/'initial-token-policy.py.txt'))['assess'];matches=0
  for c in REFERENCE['cases']:
   if c['group']!='post-result-integration-controls':continue
   raw=json.loads((HISTORY/'initial-integration'/(c['id']+'.json')).read_bytes());tr,er=inputs(c['id']);r=frozen(tr,er)
   self.assertEqual(r,raw['report']);matches+=check(frozen,c)
  self.assertEqual(matches,2)
 def test_initial_envelope_failures_reproduced(self):
  frozen=runpy.run_path(str(HISTORY/'before-boundary-token-policy.py.txt'))['assess'];matches=0
  for c in REFERENCE['cases']:
   if c['group']!='post-result-envelope-controls':continue
   original=json.loads((HISTORY/'initial-boundary'/(c['id']+'.json')).read_bytes());report=error=None
   try:report=frozen(*inputs(c['id']))
   except Exception as ex:error={'type':type(ex).__name__,'message':str(ex),'structured':isinstance(ex,ValueError)}
   with self.subTest(case=c['id']):self.assertEqual(report,original['report']);self.assertEqual(error,original['check']['error'])
   matches+=original['check']['matched']
  self.assertEqual(matches,4)
 def test_complete_response_contract(self):
  tr,er=inputs('used-all');task=json.loads(tr);evidence=json.loads(er);r=assess(tr,er)
  self.assertEqual(r['format'],'agent-crash-lab/token-policy-report-v1');self.assertEqual(r['profile'],task['profile']);self.assertEqual(r['scope'],{'closed_horizon':task['closed_horizon'],'note':task['horizon_note']});self.assertEqual(r['authority'],task['authority']);self.assertEqual(r['source'],evidence['source']);self.assertEqual(len(r['assumptions']),3)
  self.assertEqual(r['intents'][0]['recipient'],task['intents'][0]['recipient']);self.assertEqual(r['intents'][0]['burn_cap'],task['intents'][0]['max_burn']);self.assertEqual(r['assessor_sha256'],sha256((ROOT/'token_policy.py').read_bytes()).hexdigest());self.assertEqual(r['primitive_sha256'],sha256((ROOT/'token_review.py').read_bytes()).hexdigest())
 def test_bundle_exact_bytes_and_shape(self):
  tr,er=inputs('sender-deleted-burn');bundle={'format':'agent-crash-lab/token-policy-bundle-v1','task_utf8':tr.decode(),'evidence_utf8':er.decode()};self.assertEqual(api['assess_bundle'](pack(bundle)),assess(tr,er))
  for key,value in [('format','unknown'),('task_utf8',[]),('evidence_utf8',None),('task_path','secret.txt')]:
   bad={**bundle,key:value}
   with self.subTest(key=key),self.assertRaises(ValueError):api['assess_bundle'](pack(bad))
  with self.assertRaises(ValueError):api['assess_bundle'](b'{"format":"a","format":"b"}')
 def test_policy_cannot_reuse_changed_evidence(self):
  tr,er=inputs('used-all')
  with self.assertRaises(ValueError):assess(tr,er+b' ')
  with self.assertRaises(ValueError):assess(tr,b'')
 def test_missing_transaction_has_the_same_payment_contract(self):
  tr,er=inputs('used-all');original=assess(tr,er);t=json.loads(tr);t['bindings'][0]['tx_hash']='unobserved-transaction';missing=assess(pack(t),er)
  self.assertEqual(set(missing['payments'][0]),set(original['payments'][0]));self.assertEqual(missing['gate'],2);self.assertEqual(missing['payments'][0]['settlement_status'],'unknown');self.assertIsNone(missing['payments'][0]['settled'])
 def test_local_http_exact_input_boundary(self):
  import threading,urllib.request,urllib.error
  app=runpy.run_path(str(ROOT/'workbench.py'));server=app['Server'](('127.0.0.1',0));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
  def get(path):
   with urllib.request.urlopen(origin+path,timeout=10) as r:return json.loads(r.read())
  def post(raw,token=None):
   req=urllib.request.Request(origin+'/api/token-policy',data=raw,headers={'Content-Type':'application/json','X-CrashLab-Token':token or server.token})
   with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read())
  try:
   catalog=get('/api/token-policy-catalog');self.assertEqual(len(catalog['cases']),11);self.assertEqual(catalog['assessorSha256'],sha256((ROOT/'token_policy.py').read_bytes()).hexdigest())
   for c in catalog['cases']:
    b=get('/api/token-policy-input?case='+c['id']);self.assertEqual(post(pack(b)),assess(b['task_utf8'].encode(),b['evidence_utf8'].encode()))
   for raw in [b'{}',b'{bad',pack({'task_path':'private.txt'}),b'[]']:
    with self.assertRaises(urllib.error.HTTPError) as caught:post(raw)
    self.assertEqual(caught.exception.code,400);caught.exception.close()
   with self.assertRaises(urllib.error.HTTPError) as caught:post(b'{}','invalid-session')
   self.assertEqual(caught.exception.code,403);caught.exception.close()
   with self.assertRaises(urllib.error.HTTPError) as caught:get('/api/token-policy-input?case=../../private')
   self.assertEqual(caught.exception.code,404);caught.exception.close()
  finally:server.shutdown();server.server_close();thread.join(2)
 def test_cli_gate_and_default(self):
  for cid in ['used-all','sender-deleted-burn','missing-causal-descendant-100']:
   c=CASES[cid];args=[sys.executable,'-I','-S',str(ROOT/'token_policy.py'),str(ROOT/c['task']),str(ROOT/c['evidence'])]
   for flags,wanted in [([],0),(['--gate'],c['expected']['gate'])]:
    r=subprocess.run([*args,*flags],capture_output=True,timeout=15);self.assertEqual(r.returncode,wanted,r.stderr);self.assertEqual(json.loads(r.stdout),assess(*inputs(cid)))
 def test_semantic_ablations(self):
  # Identical source-informed mutation definitions retained from the research.
  # Importing the old research runner would read its workspace. Read only the
  # literal replacement dictionary via AST; do not execute that runner.
  import ast
  tree=ast.parse((HISTORY/'check_mutants.py.txt').read_text('utf-8'));node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='plans' for t in n.targets));plans=ast.literal_eval(node.value);source=(ROOT/'token_policy.py').read_text('utf-8')
  for name,changes in plans.items():
   # Atomic validation moved the increment to its own line. This is an explicit
   # source-location adaptation of the same first-FINAL-only semantic ablation.
   if name=='select-first-final-only':changes=[('self.final_observations+=1','self.final_observations+=1\n   if self.final_observations>1:return')]
   altered=source
   for before,after in changes:self.assertEqual(altered.count(before),1,name);altered=altered.replace(before,after)
   mutant={'__file__':str(ROOT/'token_policy.py'),'__name__':'semantic_mutant'};exec(compile(altered,name,'exec'),mutant)
   with self.subTest(mutant=name):self.assertTrue(any(not check(mutant['assess'],c) for c in REFERENCE['cases'] if c['group'] in ['registered-source-informed','post-baseline-protocol-controls']))

if __name__=='__main__':unittest.main()
