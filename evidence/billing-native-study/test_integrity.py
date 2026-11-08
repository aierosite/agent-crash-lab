from pathlib import Path
from hashlib import sha256
import copy,json,shutil,tempfile,unittest
from audit import H,audit
class Controls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='acl-banking-integrity-');self.p=Path(self.tmp.name)
  assert self.p.resolve().parent==Path(tempfile.gettempdir()).resolve() and self.p.name.startswith('acl-banking-integrity-')
  for name in ['LOCK.json',*json.loads((H/'LOCK.json').read_bytes())['sources']]:
   p=self.p/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(H/name,p)
  shutil.copytree(H/'actual',self.p/'actual')
 def tearDown(self):
  assert self.p.resolve().parent==Path(tempfile.gettempdir()).resolve() and self.p.name.startswith('acl-banking-integrity-');self.tmp.cleanup()
 def load(self,name):return json.loads((self.p/'actual'/name).read_bytes())
 def save(self,name,value):(self.p/'actual'/name).write_text(json.dumps(value),encoding='utf-8')
 def test_original_prefix(self):self.assertFalse(audit(self.p)[0]['collectionComplete'])
 def test_promoted_complete_collection(self):
  v=self.load('execution.json');v.update(complete=True,failure=None,casesComplete=1);self.save('execution.json',v)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_drop_unexecuted_truncated_response(self):
  v=self.load('calls.json');self.save('calls.json',v[:-1])
  with self.assertRaises(AssertionError):audit(self.p)
 def test_fabricated_paid_history_without_sdk(self):
  v=self.load('episodes.json');v[0]['history'].append({'id':8,'sender':'DE89370400440532013000','recipient':'UK12345678901234567890','amount':98.7,'subject':'Fake','date':'2022-01-01','recurring':False});self.save('episodes.json',v)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_resealed_changed_invoice_reply(self):
  v=self.load('episodes.json');step=v[0]['steps'][0];event=v[0]['hostEvents'][0];body=json.loads(step['responseUtf8']);body['content']=body['content'].replace('98.70','1.00');raw=json.dumps(body)+'\n';step.update(responseUtf8=raw,responseSha256=sha256(raw.encode()).hexdigest());event['responseUtf8']=raw;self.save('episodes.json',v)
  with self.assertRaises(AssertionError):audit(self.p)
 def test_invented_final_snapshot(self):
  v=self.load('episodes.json');v[0]['sdkSnapshot']={'op':'snapshot','case':v[0]['id'],'payer':'181000','bill':'0','attacker':'0','other':'0','supply':'181000'};self.save('episodes.json',v)
  with self.assertRaises(AssertionError):audit(self.p)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls));(H/'INTEGRITY-CONTROLS.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'tamperingRejected':5,'sameAuthor':True,'basis':'Actual raw collected prefix copied to verified owned disposable directories; no model or SDK effects'},indent=2)+'\n',encoding='utf-8');raise SystemExit(0 if result.wasSuccessful() else 1)
