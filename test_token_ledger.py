"""Registered external-value and scope controls for a separate ledger diagnostic."""
from pathlib import Path
from hashlib import sha256
import json,runpy,unittest
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'verification/token-ledger-study'
api=runpy.run_path(str(ROOT/'token_ledger.py'))

class ReportedLedger(unittest.TestCase):
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
