"""Registered external-value and scope controls for a separate ledger diagnostic."""
from pathlib import Path
from hashlib import sha256
import json,runpy,unittest,threading,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'verification/token-ledger-study'
api=runpy.run_path(str(ROOT/'token_ledger.py'))

class ReportedLedger(unittest.TestCase):
 def test_new_catalog_example_and_legacy_api_are_distinct(self):
  app=runpy.run_path(str(ROOT/'workbench.py'));server=app['Server'](('127.0.0.1',0));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  try:
   with urllib.request.urlopen(base+'/api/token-ledger-catalog',timeout=5) as response:c=json.load(response)
   self.assertEqual(len(c['recordings']),9);entry=next(r for r in c['recordings'] if r['id']=='declared-ledger-conflict')
   with urllib.request.urlopen(base+'/api/token-ledger-recording?case='+entry['id'],timeout=5) as response:raw=response.read()
   self.assertEqual(sha256(raw).hexdigest(),entry['sha256']);self.assertEqual(c['assessorSha256'],sha256((ROOT/'token_ledger.py').read_bytes()).hexdigest());self.assertEqual(c['baseAssessorSha256'],sha256((ROOT/'token_review.py').read_bytes()).hexdigest())
   request=urllib.request.Request(base+'/api/token-ledger-review',data=raw,headers={'Content-Type':'application/json','X-CrashLab-Token':server.token})
   with urllib.request.urlopen(request,timeout=5) as response:r=json.load(response)
   self.assertEqual(r,api['review'](raw));self.assertEqual(r['steps'][0]['reported_ledger']['after_difference'],'3');self.assertEqual(r['conclusion'],'inconclusive')
   with urllib.request.urlopen(base+'/api/token-catalog',timeout=5) as response:old=json.load(response)
   self.assertEqual(len(old['recordings']),8);self.assertNotIn(entry['id'],[r['id'] for r in old['recordings']])
   for path in ['/api/token-recording?case=declared-ledger-conflict','/api/token-ledger-recording?case=../token_review.py']:
    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+path,timeout=5)
    self.assertEqual(error.exception.code,404);error.exception.close()
  finally:server.shutdown();server.server_close();thread.join(3)
 def test_registered_eight_endpoint_controls(self):
  raw=(DATA/'cases.json').read_bytes();reg=json.loads((DATA/'registration.json').read_bytes())
  self.assertEqual(sha256(raw).hexdigest(),reg['casesSha256']);cases=json.loads(raw);self.assertEqual(len(cases),8)
  for case in cases:
   with self.subTest(case=case['id']):
    r=api['review'](api['pack'](case['input']));self.assertEqual(r['format'],'agent-crash-lab/token-review-v3');s=r['steps'][0]
    self.assertEqual(s['reported_ledger'],{'status':case['expectedStatus'],'before_difference':case['expectedBeforeDifference'],'after_difference':case['expectedAfterDifference']})
    if case['expectedStatus']!='matches':
     self.assertEqual(s['conclusion'],'inconclusive');self.assertIsNone(s['backing_shortfall']);self.assertIsNone(s['rights_debit_without_transfer']);self.assertEqual(s['ledger_relation'],'unknown')
    if case['expectedStatus']=='not-declared':self.assertFalse(any('this single-owner ledger' in reason for reason in s['reasons']))

if __name__=='__main__':unittest.main()
