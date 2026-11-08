"""Replay externally authored facts against a source-informed, same-author arithmetic reference."""
from pathlib import Path
from hashlib import sha256
import copy,json,runpy,unittest,threading,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
api=runpy.run_path(str(ROOT/'token_review.py'));review=api['review'];pack=api['pack'];Error=api['ReviewError']
STUDY=ROOT/'verification/token-study'
def fixture(name):return json.loads((STUDY/(name+'.json')).read_bytes())
def projection(r):
 return {'conclusion':r['conclusion'],'heldDeltas':[s['held_delta'] for s in r['steps']],
  'rightsDeltas':[s['rights_delta'] for s in r['steps']],'grossVaultOut':[s['gross_out'] for s in r['steps']],
  'reduction':[s['entitlement_reduction'] for s in r['steps']]}
def registered_checks(fn=review):
 reg=json.loads((STUDY/'registration.json').read_bytes());expected=json.loads((STUDY/'reference.json').read_bytes())['cases'];rows=[]
 assert sha256((STUDY/'plan.json').read_bytes()).hexdigest()==reg['planSha256']
 assert sha256((STUDY/'reference.json').read_bytes()).hexdigest()==reg['referenceSha256']
 assert sha256((ROOT/'tools/import_token_archive.py').read_bytes()).hexdigest()==reg['importerSha256']
 for name,digest in reg['inputs'].items():
  raw=(STUDY/name).read_bytes();assert sha256(raw).hexdigest()==digest
  r=fn(raw);actual=projection(r);wanted=expected[name.removesuffix('.json')]
  rows.append({'case':r['recording_id'],'actual':actual,'expected':wanted,'matches':actual==wanted,'reportSha256':sha256(pack(r)).hexdigest()})
 return rows
def mutations():
 source=(ROOT/'token_review.py').read_text('utf-8');out=[]
 replacements={
  'drop-reserved-rights':("s['credit']+s['pending']+s['reserved']","s['credit']+s['pending']"),
  'backing-only':(" or conservation!='preserved'",''),
  'ignore-outgoing-refund':('net=inbound-outbound;agrees=delta==net','net=inbound;agrees=delta==net'),
 }
 for name,(old,new) in replacements.items():
  assert source.count(old)==1;mutant=source.replace(old,new);ns={'__name__':'mutant','__file__':str(ROOT/'token_review.py')};exec(compile(mutant,name,'exec'),ns)
  rows=registered_checks(ns['review']);out.append({'id':name,'sha256':sha256(mutant.encode()).hexdigest(),'caughtBy':[r['case'] for r in rows if not r['matches']]})
 return out
class TokenReview(unittest.TestCase):
 def test_registered_reference(self):
  rows=registered_checks();self.assertEqual(len(rows),5);self.assertTrue(all(r['matches'] for r in rows),rows)
 def test_semantic_mutants(self):
  rows=mutations();self.assertEqual(len(rows),3);self.assertTrue(all(r['caughtBy'] for r in rows),rows)
 def test_missing_receipt(self):
  d=fixture('upstream-healthy');d['steps'][1]['transactions'][0]['result']['receipts_outcome'].pop()
  r=review(pack(d));self.assertEqual(r['steps'][1]['conclusion'],'inconclusive');self.assertIsNone(r['steps'][1]['entitlement_reduction'])
 def test_missing_transaction(self):
  d=fixture('upstream-failed-withdrawal');d['steps'][-1]['transactions']=[]
  self.assertEqual(review(pack(d))['steps'][-1]['conclusion'],'inconclusive')
 def test_foreign_emitter(self):
  d=fixture('upstream-healthy')
  for row in d['steps'][1]['transactions'][0]['result']['receipts_outcome']:
   if any('EVENT_JSON:' in log for log in row['outcome']['logs']):row['outcome']['executor_id']='forged.testnet'
  r=review(pack(d))['steps'][1];self.assertEqual(r['state_event_agreement'],'contradicts');self.assertEqual(r['gross_out'],'0');self.assertEqual(r['rights_conservation'],'unknown')
 def test_code_change(self):
  d=fixture('ai-payment');d['asset']['deployed_after']='changed'
  self.assertEqual(review(pack(d))['conclusion'],'inconclusive')
 def test_missing_scope(self):
  d=fixture('ai-payment');d['scope']['closed_intervals']=False
  self.assertEqual(review(pack(d))['conclusion'],'inconclusive')
 def test_duplicate_receipt(self):
  d=fixture('ai-payment');r=d['steps'][0]['transactions'][0]['result']['receipts_outcome'];r.append(copy.deepcopy(r[0]))
  with self.assertRaisesRegex(Error,'receipt ID'):review(pack(d))
 def test_duplicate_json_key(self):
  with self.assertRaisesRegex(Error,'repeats a JSON'):review(b'{"format":"x","format":"y"}')
 def test_exact_large_amount(self):
  d=fixture('ai-payment');step=d['steps'][-1];d['steps']=[step];n=2**100+123
  for key in ['credit','reserved','pending','liabilities']:step['before'][key]=step['after'][key]='0'
  step['before'].update(held=str(n),credit=str(n),liabilities=str(n));step['after'].update(held='0',credit='0',liabilities='0')
  for row in step['transactions'][0]['result']['receipts_outcome']:
   logs=row['outcome']['logs']
   for i,line in enumerate(logs):
    if line.startswith('EVENT_JSON:'):
     e=json.loads(line[len('EVENT_JSON:'):]);e['data'][0]['amount']=str(n);logs[i]='EVENT_JSON:'+pack(e).decode()
  r=review(pack(d));self.assertEqual(r['conclusion'],'recorded-consistent');self.assertEqual(r['steps'][0]['gross_out'],str(n))
 def test_failed_log_is_not_payment(self):
  d=fixture('upstream-auth');s=d['steps'][-1]
  node=next(x for x in s['transactions'][0]['result']['receipts_outcome'] if 'Failure' in x['outcome']['status'])
  node['outcome']['executor_id']=d['asset']['contract'];node['outcome']['logs']=['EVENT_JSON:'+pack({'standard':'nep141','version':'1.0.0','event':'ft_transfer','data':[{'old_owner_id':d['vault'],'new_owner_id':'sink.testnet','amount':'1'}]}).decode()]
  r=review(pack(d));self.assertEqual(r['conclusion'],'recorded-consistent');self.assertEqual(r['steps'][-1]['gross_out'],'0');self.assertEqual(r['steps'][-1]['ignored_event_logs'],1)
 def test_nonfinal(self):
  d=fixture('ai-payment');d['steps'][-1]['transactions'][0]['result']['final_execution_status']='EXECUTED_OPTIMISTIC'
  self.assertEqual(review(pack(d))['steps'][-1]['conclusion'],'inconclusive')
 def test_false_or_noncanonical_amount(self):
  for value in [False,'01','-1',str(2**128),'1.5',1]:
   with self.subTest(value=value):
    d=fixture('ai-payment');d['steps'][0]['before']['held']=value
    with self.assertRaises(Error):review(pack(d))
 def test_reported_liability_mismatch(self):
  d=fixture('ai-payment');d['steps'][1]['after']['liabilities']='999'
  self.assertEqual(review(pack(d))['steps'][1]['conclusion'],'inconclusive')
 def test_malformed_event(self):
  d=fixture('ai-payment');s=d['steps'][-1]
  for row in s['transactions'][0]['result']['receipts_outcome']:
   if any(x.startswith('EVENT_JSON:') for x in row['outcome']['logs']):row['outcome']['logs']=['EVENT_JSON:{"standard":"nep141","amount":"1","amount":"2"}']
  self.assertEqual(review(pack(d))['steps'][-1]['conclusion'],'inconclusive')
 def test_top_level_unknown_is_not_final_success(self):
  d=fixture('ai-payment');d['steps'][-1]['transactions'][0]['result']['status']={'Unknown':None}
  self.assertEqual(review(pack(d))['steps'][-1]['conclusion'],'inconclusive')
 def test_cycle(self):
  d=fixture('ai-payment');r=d['steps'][0]['transactions'][0]['result'];r['transaction_outcome']['outcome']['receipt_ids']=[r['transaction']['hash']]
  with self.assertRaisesRegex(Error,'cycle'):review(pack(d))
 def test_actual_local_api_preserves_exact_bytes(self):
  app=runpy.run_path(str(ROOT/'workbench.py'));server=app['Server'](('127.0.0.1',0));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base='http://127.0.0.1:'+str(server.server_port)
  def post(raw,token):
   req=urllib.request.Request(base+'/api/token-review',data=raw,headers={'Content-Type':'application/json','X-CrashLab-Token':token})
   with urllib.request.urlopen(req,timeout=5) as response:return json.loads(response.read())
  try:
   for name in ['upstream-healthy','upstream-refund','upstream-failed-withdrawal','upstream-auth','ai-payment']:
    with self.subTest(name=name):
     raw=(STUDY/(name+'.json')).read_bytes();self.assertEqual(post(raw,server.token),review(raw))
   with self.assertRaises(urllib.error.HTTPError) as caught:post(b'{}','wrong-session')
   self.assertEqual(caught.exception.code,403)
   caught.exception.close()
   with self.assertRaises(urllib.error.HTTPError) as caught:post(b'{"format":1,"format":2}',server.token)
   self.assertEqual(caught.exception.code,400)
   caught.exception.close()
   with urllib.request.urlopen(base+'/api/token-catalog',timeout=5) as response:c=json.loads(response.read())
   self.assertEqual(len(c['recordings']),5)
   for entry in c['recordings']:
    with urllib.request.urlopen(base+'/api/token-recording?case='+entry['id'],timeout=5) as response:raw=response.read()
    self.assertEqual(len(raw),entry['bytes']);self.assertEqual(sha256(raw).hexdigest(),entry['sha256'])
   with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(base+'/api/token-recording?case=../token_review.py',timeout=5)
   self.assertEqual(caught.exception.code,404)
   caught.exception.close()
  finally:server.shutdown();server.server_close();thread.join(2)
if __name__=='__main__':unittest.main()
