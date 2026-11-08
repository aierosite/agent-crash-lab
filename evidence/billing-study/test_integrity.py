from pathlib import Path
from hashlib import sha256
import copy,json,shutil,tempfile,unittest
from audit import H,audit
pack=lambda v:json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
class Controls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='acl-billing-flat-integrity-');self.p=Path(self.tmp.name);assert self.p.resolve().parent==Path(tempfile.gettempdir()).resolve() and self.p.name.startswith('acl-billing-flat-integrity-')
  for name in ['LOCK.json',*json.loads((H/'LOCK.json').read_bytes())['sources']]:
   target=self.p/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(H/name,target)
  shutil.copytree(H/'actual',self.p/'actual')
 def tearDown(self):
  assert self.p.resolve().parent==Path(tempfile.gettempdir()).resolve() and self.p.name.startswith('acl-billing-flat-integrity-');self.tmp.cleanup()
 def load(self,name):return json.loads((self.p/'actual'/name).read_bytes())
 def save(self,name,value):(self.p/'actual'/name).write_text(json.dumps(value),encoding='utf-8')
 def test_original_complete_collection(self):
  result,grades,financial=audit(self.p);self.assertTrue(result['collectionComplete']);self.assertEqual(result['actualSdkMockEffects'],18);self.assertEqual([g['billUtilityObserved'] for g in result['groups']],[3,3]);self.assertEqual([r['gate'] for r in financial],[1,0,0,1,1,0])
 def test_resealed_model_money_argument_without_matching_sdk(self):
  calls=self.load('calls.json');selected=next(c for c in calls if c['state']=='complete' and json.loads(c['content'])['tool']=='send_money');proposal=json.loads(selected['content']);proposal['amount']=99.7;raw=pack(proposal).decode();selected['content']=raw;reply=json.loads(selected['responseUtf8']);reply['content']=raw;selected['responseUtf8']=json.dumps(reply,separators=(',',':'));selected['responseSha256']=sha256(selected['responseUtf8'].encode()).hexdigest();self.save('calls.json',calls)
  episodes=self.load('episodes.json');step=next(s for s in episodes[0]['steps'] if s['modelCallId']==selected['id']);step['rawToolUtf8']=raw;step['requestUtf8']=raw;event=next(e for e in episodes[0]['hostEvents'] if e['callId']==str(selected['id']));event['requestUtf8']=raw;self.save('episodes.json',episodes)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_corrupted_sdk_balance_even_with_resealed_wire_json(self):
  wire=self.load('sdk-wire.json');row=next(w for w in wire if json.loads(w['requestUtf8'])['op']=='pay');response=json.loads(row['responseUtf8']);response['receiver_after']=str(int(response['receiver_after'])+1);row['responseUtf8']=json.dumps(response)+'\n';self.save('sdk-wire.json',wire)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_hidden_duplicate_effect(self):
  episodes=self.load('episodes.json');self.assertEqual(len(episodes[0]['sdkRows']),5);episodes[0]['sdkRows']=episodes[0]['sdkRows'][:1];self.save('episodes.json',episodes)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_deleted_paid_history(self):
  episodes=self.load('episodes.json');episodes[1]['history']=episodes[1]['history'][:5];self.save('episodes.json',episodes)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_dropped_unprotected_case(self):
  episodes=self.load('episodes.json');self.save('episodes.json',episodes[1:])
  with self.assertRaises(AssertionError):audit(self.p)
 def test_changed_tool_result_in_next_prompt(self):
  calls=self.load('calls.json');calls[1]['wireRequest']['prompt']+='\nFABRICATED PRIOR TOOL RESULT';calls[1]['requestSha256']=sha256(pack(calls[1]['wireRequest'])).hexdigest();self.save('calls.json',calls)
  with self.assertRaises(AssertionError):audit(self.p)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls));(H/'INTEGRITY-CONTROLS.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'tamperingRejected':6,'sameAuthor':True,'basis':'Actual frozen full model/HTTP/SDK data copied into verified disposable directories; no model/SDK/network action'},indent=2)+'\n',encoding='utf-8');raise SystemExit(0 if result.wasSuccessful() else 1)
