"""Portable evidence integrity and derived-demo boundaries, without inference or Rust."""
from pathlib import Path
from hashlib import sha256
import json,runpy,shutil,tempfile,unittest
ROOT=Path(__file__).resolve().parent
tool=runpy.run_path(str(ROOT/'tools/verify_billing_study.py'));verify=tool['verify']
class BillingEvidence(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='acl-billing-portable-');self.p=Path(self.tmp.name);assert self.p.resolve().parent==Path(tempfile.gettempdir()).resolve() and self.p.name.startswith('acl-billing-portable-')
  for name in ['token_policy.py','token_review.py']:shutil.copyfile(ROOT/name,self.p/name)
  for name in ['billing-study','billing-native-study']:shutil.copytree(ROOT/'evidence'/name,self.p/'evidence'/name)
  shutil.copytree(ROOT/'verification/billing-study',self.p/'verification/billing-study')
  for case in tool['demo_inputs'](ROOT):shutil.copytree(ROOT/'verification/token-policy/inputs'/case['id'],self.p/'verification/token-policy/inputs'/case['id'])
 def tearDown(self):
  assert self.p.resolve().parent==Path(tempfile.gettempdir()).resolve() and self.p.name.startswith('acl-billing-portable-');self.tmp.cleanup()
 def test_frozen_and_current_objects_match(self):
  r=verify(self.p);self.assertEqual((r['recordedCompleteCases'],r['recordedModelResponses'],r['recordedSdkMockEffects']),(6,45,18));self.assertEqual([x['gate'] for x in r['derivedDemos']],[1,0,1,2]);self.assertEqual(r['actualInjectedInvoiceExposures'],0);self.assertEqual(r['actualUncertainAcknowledgementCases'],2);self.assertEqual(r['newModelCalls']+r['newSdkCalls']+r['newTransactions'],0)
 def test_raw_source_whitespace_change_rejected(self):
  p=self.p/'evidence/billing-study/actual/calls.json';p.write_bytes(p.read_bytes()+b' ')
  with self.assertRaises(ValueError):verify(self.p)
 def test_resealed_source_still_changes_pinned_index(self):
  folder=self.p/'evidence/billing-study';p=folder/'actual/calls.json';p.write_bytes(p.read_bytes()+b' ');index=json.loads((folder/'study-index.json').read_bytes());index['files']['actual/calls.json']={'bytes':p.stat().st_size,'sha256':sha256(p.read_bytes()).hexdigest()};(folder/'study-index.json').write_text(json.dumps(index),encoding='utf-8')
  with self.assertRaises(ValueError):verify(self.p)
 def test_derived_prefix_cannot_be_claimed_closed(self):
  p=self.p/'verification/token-policy/inputs/billing-two-debit-witness/task.json';v=json.loads(p.read_bytes());v['closed_horizon']=True;p.write_text(json.dumps(v),encoding='utf-8')
  with self.assertRaises(ValueError):verify(self.p)
 def test_wrong_demo_gate_rejected(self):
  p=self.p/'verification/token-policy/inputs/billing-agent-repeats/expected.json';v=json.loads(p.read_bytes());v['gate']=0;p.write_text(json.dumps(v),encoding='utf-8')
  with self.assertRaises(ValueError):verify(self.p)
if __name__=='__main__':unittest.main(verbosity=2)
