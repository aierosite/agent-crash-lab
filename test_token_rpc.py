"""Portable raw-query/receipt binding regressions, including preserved first reader failures."""
from pathlib import Path
from hashlib import sha256
import copy,json,runpy,shutil,tempfile,unittest
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'verification/rpc-study';RECORDINGS=ROOT/'verification/token-study';MODULE=ROOT/'tools/verify_token_rpc.py';api=runpy.run_path(str(MODULE))
def statuses(result):return {c['case']:c['operationReference']['status'] for c in result['cases']}
EXPECTED={'upstream-failed-withdrawal':'failed','ai-payment':'passed'}
def payload(doc):
 return next(r for r in doc['result']['receipts'] if r['receiver_id'].startswith('token.') and r['predecessor_id'].startswith('vault.'))
def change_recipient(doc):
 import base64
 fc=payload(doc)['receipt']['Action']['actions'][0]['FunctionCall'];a=json.loads(base64.b64decode(fc['args']));a['receiver_id']='wrong.testnet';fc['args']=base64.b64encode(json.dumps(a).encode()).decode()
def mutate(folder,target,kind,fn):
 path=folder/target/(kind+'.json');d=json.loads(path.read_bytes());fn(d);path.write_text(json.dumps(d,separators=(',',':')),'utf-8');p=path.parent/'observation.json';o=json.loads(p.read_bytes());o[kind+'Sha256']=sha256(path.read_bytes()).hexdigest()
 if kind=='response':o['responseBytes']=path.stat().st_size
 p.write_text(json.dumps(o,separators=(',',':')),'utf-8')
class TokenRpc(unittest.TestCase):
 def workspace(self):
  temp=tempfile.TemporaryDirectory(prefix='rpc-test-',dir=ROOT);folder=Path(temp.name).resolve();self.assertTrue(folder.is_relative_to(ROOT.resolve()));self.addCleanup(temp.cleanup);captures=folder/'captures';shutil.copytree(DATA,captures);return captures
 def test_actual_corroboration_and_reference(self):
  result=api['verify'](DATA,RECORDINGS);self.assertEqual(statuses(result),EXPECTED);self.assertEqual(result['capturedReadRequests'],25);self.assertEqual(result['replayNetworkCalls'],0);self.assertFalse(result['signatureOrStateProofVerified']);self.assertFalse(result['independentGrading'])
  self.assertTrue(all(c['operationReference']['rootSucceeded'] for c in result['cases']));self.assertEqual(result['cases'][0]['operationReference']['payout']['outcome'],'Failure')
  catalog=json.loads((ROOT/'web/catalog.json').read_bytes());self.assertEqual(result['datasetSha256'],catalog['sourceCorroboration']['datasetSha256'])
 def test_resealed_original_structural_controls(self):
  old=runpy.run_path(str(DATA/'control-reader-v1.py.txt'))
  for name,target,kind,change in old['PLANS']:
   with self.subTest(control=name):
    captures=self.workspace();mutate(captures,target,kind,change)
    with self.assertRaises((ValueError,KeyError,TypeError)):api['verify'](captures,RECORDINGS)
 def test_preserved_initial_and_corrected_reader_results(self):
  helper=runpy.run_path(str(DATA/'control-reader-v1.py.txt'));g=helper['evaluate'].__globals__;g['ROOT']=DATA;g['RECORDINGS']=RECORDINGS
  plan=json.loads((DATA/'CONTROLS-PLAN.json').read_bytes());self.assertEqual(sha256((DATA/'control-reader-v1.py.txt').read_bytes()).hexdigest(),plan['controlSourceSha256'])
  initial=helper['evaluate'](DATA/'initial-verifier.py.txt');corrected=helper['evaluate'](DATA/'corrected-reader23.py.txt')
  self.assertEqual((initial['rejected'],initial['total']),(11,16));self.assertEqual((corrected['rejected'],corrected['total']),(16,16))
  self.assertEqual([r['id'] for r in initial['controls'] if not r['rejected']],['rpc-result-error','duplicate-receipt','query-height-float','header-height-float','transaction-gas-float'])
 def test_receipt_details_binding(self):
  target='receipt-details/25-allowed-tx-status'
  controls=[('recipient',change_recipient),('signer',lambda d:payload(d)['receipt']['Action'].update(signer_id='wrong.testnet')),('receiver',lambda d:payload(d).update(receiver_id='wrong.testnet')),('duplicate',lambda d:d['result']['receipts'].append(copy.deepcopy(payload(d)))),('different-outcome',lambda d:d['result']['receipts_outcome'][0]['outcome'].update(gas_burnt=0))]
  for name,change in controls:
   with self.subTest(control=name):
    captures=self.workspace();mutate(captures,target,'response',change)
    with self.assertRaises((ValueError,KeyError,TypeError)):api['verify'](captures,RECORDINGS)
 def test_missing_body_keeps_reference_inconclusive(self):
  captures=self.workspace();mutate(captures,'receipt-details/24-failed-tx-status','response',lambda d:d['result']['receipts'].remove(payload(d)))
  result=api['verify'](captures,RECORDINGS);row=next(c for c in result['cases'] if c['case']=='upstream-failed-withdrawal');self.assertEqual(row['operationReference']['status'],'inconclusive');self.assertIsNone(row['operationReference']['payout']);self.assertTrue(row['transactionOutcomeProjectionMatches']);self.assertEqual(statuses(result)['ai-payment'],'passed')
 def test_reference_semantic_mutants(self):
  source=MODULE.read_text('utf-8');changes={
   'root-success-only':("reference['status']='passed' if rights(after)==expected_rights else 'failed'","reference['status']='passed' if reference['rootSucceeded'] else 'failed'"),
   'omit-reservation':("rights=lambda p:sum(int(p[k]) for k in ['credit','pending','reserved'])","rights=lambda p:sum(int(p[k]) for k in ['credit','pending'])"),
  }
  for name,(old,new) in changes.items():
   with self.subTest(mutant=name):
    self.assertEqual(source.count(old),1);captures=self.workspace();path=captures.parent/(name+'.py');path.write_bytes(source.replace(old,new).encode());m=runpy.run_path(str(path));result=m['verify'](DATA,RECORDINGS);self.assertNotEqual(statuses(result),EXPECTED)
 def test_exact_input_binding_and_local_api(self):
  import threading,urllib.request,urllib.error
  app=runpy.run_path(str(ROOT/'workbench.py'));server=app['Server'](('127.0.0.1',0));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  def post(body,token):
   req=urllib.request.Request(base+'/api/token-source-check',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-CrashLab-Token':token})
   with urllib.request.urlopen(req,timeout=10) as response:return json.loads(response.read())
  try:
   for cid in EXPECTED:
    digest=sha256((RECORDINGS/(cid+'.json')).read_bytes()).hexdigest();body={'recording_sha256':digest};self.assertEqual(post(body,server.token),app['token_source_check'](body))
   changed=json.loads((RECORDINGS/'ai-payment.json').read_bytes());changed['id']='same-data-different-bytes';digest=sha256(json.dumps(changed).encode()).hexdigest();self.assertEqual(post({'recording_sha256':digest},server.token)['status'],'not-in-study')
   with self.assertRaises(urllib.error.HTTPError) as e:post({'recording_sha256':'0'*64},'wrong')
   self.assertEqual(e.exception.code,403);e.exception.close()
   path='verification/rpc-study/04-failed-before-token-state/response.json'
   with urllib.request.urlopen(base+'/api/token-source-file?name='+path,timeout=5) as response:self.assertEqual(response.read(),(ROOT/path).read_bytes())
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/token-source-file?name=../../session.json',timeout=5)
   self.assertEqual(e.exception.code,404);e.exception.close()
  finally:server.shutdown();server.server_close();thread.join(2)
if __name__=='__main__':unittest.main()
