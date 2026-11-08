"""Caller-workflow and raw-evidence boundary checks; no network/model/transactions."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy,json,os,runpy,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parent;api=runpy.run_path(str(ROOT/'token_capture.py'));create=api['create'];review=api['review'];pack=api['pack'];CaptureError=api['CaptureError']
FIXTURES=ROOT/'verification/token-policy/inputs'
SOURCE={'kind':'synthetic','note':'Constructed registered fixture; no network observations or transactions.'}

def inputs(name):
 base=FIXTURES/name;t=json.loads((base/'task.json').read_bytes());e=json.loads((base/'evidence.json').read_bytes());t.pop('evidence_sha256');t['format']='agent-crash-lab/token-policy-template-v1'
 records=[(r['id'],json.dumps(r['request'],ensure_ascii=True,indent=2).replace('\n','\r\n').encode(),json.dumps(r['response'],ensure_ascii=True,indent=1).encode()+b'\n') for r in e['observations']]
 return pack(t),records

class CaptureWorkflow(unittest.TestCase):
 def test_recorded_public_browser_compatibility(self):
  result=runpy.run_path(str(ROOT/'tools/verify_capture.py'))['verify']();self.assertEqual(result['observedFullBrowserReportsMatched'],4);self.assertEqual(result['originalRawFilesVerified'],24)
 def test_declared_allowed_and_breached_policies(self):
  for name,gate in [('allowed-split-payments',0),('independent-equal-price-intents',0),('repeated-payment-breaches-cap',1),('missing-causal-descendant-100',2)]:
   with self.subTest(case=name),TemporaryDirectory() as temp:
    raw,records=inputs(name);dest=Path(temp)/'captured';r=create(dest,raw,SOURCE,records)
    self.assertEqual(r['gate'],gate);self.assertTrue(r['assessment_accepted']);self.assertTrue(r['source_integrity']['matched'])
    for index,(_,req,res) in enumerate(records):self.assertEqual((dest/f'raw/{index:03d}-request.json').read_bytes(),req);self.assertEqual((dest/f'raw/{index:03d}-response.json').read_bytes(),res)
    again,bundle=review(dest);self.assertEqual(again,r);self.assertEqual(api['POLICY']['assess_bundle'](bundle),r['assessment'])
 def test_bad_raw_reply_is_preserved_and_keeps_horizon_open(self):
  for bad in [b'<html>503 unavailable</html>',b'\xff\xfe\x00',b'{"id":1,"id":1}',b'[]']:
   with self.subTest(raw=bad),TemporaryDirectory() as temp:
    template,records=inputs('allowed-split-payments');dest=Path(temp)/'capture';records.append(('bad-raw',b'{}',bad));r=create(dest,template,SOURCE,records)
    self.assertEqual(r['gate'],2);self.assertTrue(r['assessment_accepted']);self.assertFalse(r['effective_closed_horizon']);self.assertEqual(len(r['uninterpreted_records']),1)
    self.assertEqual((dest/f'raw/{len(records)-1:03d}-response.json').read_bytes(),bad)
    bundle=json.loads((dest/'payment-bundle.json').read_bytes());e=json.loads(bundle['evidence_utf8']);self.assertEqual(len(e['observations']),len(records)-1)
    self.assertIn('all original raw pairs remain',e['source']['note']);self.assertIn('forced an open horizon',json.loads(bundle['task_utf8'])['horizon_note'])
 def test_known_excess_survives_unrelated_uninterpretable_reply(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('repeated-payment-breaches-cap');records.append(('bad-raw',b'{}',b'not JSON'));r=create(Path(temp)/'capture',template,SOURCE,records)
   self.assertEqual(r['gate'],1);self.assertFalse(r['effective_closed_horizon']);self.assertTrue(any(i['gross_status']=='breached' for i in r['assessment']['intents']))
 def test_full_length_original_notes_do_not_hide_known_excess(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('repeated-payment-breaches-cap');value=json.loads(template);value['horizon_note']='h'*2048;template=pack(value);source={'kind':'synthetic','note':'s'*2048};records.append(('bad-raw',b'{}',b'<html>failure</html>'));dest=Path(temp)/'capture';r=create(dest,template,source,records)
   self.assertEqual(r['gate'],1);self.assertTrue(r['assessment_accepted']);self.assertEqual((dest/'policy-template.json').read_bytes(),template);self.assertEqual(r['source'],source)
   self.assertIn('Original source note retained',r['assessment']['source']['note']);self.assertIn('Original horizon note retained',r['assessment']['scope']['note']);self.assertFalse(r['effective_closed_horizon'])
 def test_initial_long_note_failure_reproduces_exactly(self):
  history=ROOT/'evidence/capture-study';record=json.loads((history/'LONG-NOTE-COUNTEREXAMPLE.json').read_bytes());from hashlib import sha256
  self.assertEqual(sha256((history/'initial/token_capture.py').read_bytes()).hexdigest(),record['prototypeSourceSha256']);old=runpy.run_path(str(history/'initial/token_capture.py'))
  with TemporaryDirectory() as temp:
   template,records=inputs('repeated-payment-breaches-cap');value=json.loads(template);value['horizon_note']='h'*2048;source={'kind':'synthetic','note':'s'*2048};records.append(('bad-raw',b'{}',b'<html>failure</html>'))
   original=old['create'](Path(temp)/'capture',pack(value),source,records);self.assertEqual(original,record['actual']);self.assertEqual(original['gate'],2)
 def test_reindexed_source_pointer_maps_back_to_original_raw_reply(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('allowed-split-payments');records.insert(0,('bad-first',b'{}',b'bad'));r=create(Path(temp)/'capture',template,SOURCE,records)
   self.assertEqual(r['supported_records'][0],{'capture_index':1,'observation_index':0,'id':records[1][0]})
   event=r['assessment']['known_custody_events'][0]
   for pointer in event['source_refs']:
    tokens=pointer.split('/')[1:];self.assertEqual(tokens[:3],['observations','0','response']);value=json.loads(records[1][2])
    for token in tokens[3:]:
     token=token.replace('~1','/').replace('~0','~');value=value[int(token)] if type(value) is list else value[token]
    self.assertTrue(value.startswith('EVENT_JSON:'));self.assertIn(event['amount'],value)
 def test_changed_raw_whitespace_cannot_inherit_export(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('allowed-split-payments');dest=Path(temp)/'capture';create(dest,template,SOURCE,records);export=(dest/'payment-bundle.json').read_bytes();raw=dest/'raw/000-response.json';raw.write_bytes(raw.read_bytes()+b' ')
   with self.assertRaisesRegex(CaptureError,'Original raw bytes changed'):review(dest)
   self.assertEqual((dest/'payment-bundle.json').read_bytes(),export)
 def test_unsafe_path_and_changed_export_rejected(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('allowed-split-payments');dest=Path(temp)/'capture';create(dest,template,SOURCE,records);header=json.loads((dest/'capture.json').read_bytes());original=(dest/'capture.json').read_bytes();header['records'][0]['response']['file']='../outside.json';(dest/'capture.json').write_bytes(pack(header))
   with self.assertRaisesRegex(CaptureError,'expected generated path'):review(dest)
   (dest/'capture.json').write_bytes(original);out=dest/'payment-bundle.json';out.write_bytes(out.read_bytes()+b' ')
   with self.assertRaisesRegex(CaptureError,'Stored export differs'):review(dest)
 def test_existing_directory_and_duplicate_ids_do_not_overwrite(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('allowed-split-payments');root=Path(temp);marker=root/'mine.txt';marker.write_bytes(b'keep')
   with self.assertRaisesRegex(CaptureError,'already exists'):create(root,template,SOURCE,records)
   self.assertEqual(marker.read_bytes(),b'keep');self.assertFalse((root/'capture.json').exists())
   duplicate=[records[0],records[0]]
   with self.assertRaisesRegex(CaptureError,'unique'):create(root/'new',template,SOURCE,duplicate)
   self.assertFalse((root/'new').exists())
 def test_invalid_policy_keeps_original_inputs(self):
  with TemporaryDirectory() as temp:
   _,records=inputs('allowed-split-payments');dest=Path(temp)/'capture';bad=b'{"format":1,"format":2}';r=create(dest,bad,SOURCE,records)
   self.assertEqual(r['gate'],2);self.assertFalse(r['assessment_accepted']);self.assertIsNone(r['assessment']);self.assertTrue(r['assessment_error']);self.assertEqual((dest/'policy-template.json').read_bytes(),bad);self.assertFalse((dest/'payment-bundle.json').exists())
 def test_count_individual_and_aggregate_bounds_create_nothing(self):
  with TemporaryDirectory() as temp:
   root=Path(temp);template,records=inputs('allowed-split-payments')
   attempts=[[(str(i),b'{}',b'{}') for i in range(129)],[('large',b'{}',b' '*(2*1024*1024+1))],[(str(i),b'{}',b' '*(2*1024*1024)) for i in range(4)]]
   for index,bad in enumerate(attempts):
    with self.subTest(bound=index),self.assertRaises(CaptureError):create(root/str(index),template,SOURCE,bad)
    self.assertFalse((root/str(index)).exists())
 def test_symlink_raw_and_index_are_not_followed(self):
  with TemporaryDirectory() as temp:
   template,records=inputs('allowed-split-payments');root=Path(temp);dest=root/'capture';create(dest,template,SOURCE,records);raw=dest/'raw/000-response.json';outside=root/'outside.json';outside.write_bytes(raw.read_bytes());raw.unlink()
   try:os.symlink(outside,raw)
   except (OSError,NotImplementedError):self.skipTest('Symlink creation is unavailable on this host.')
   with self.assertRaisesRegex(CaptureError,'symlink'):review(dest)
   raw.unlink();raw.write_bytes(outside.read_bytes());index=dest/'capture.json';saved=root/'index.json';saved.write_bytes(index.read_bytes());index.unlink();os.symlink(saved,index)
   with self.assertRaisesRegex(CaptureError,'index must not be a symlink'):review(dest)
 def test_cli_create_and_check_use_gate_exit_and_exact_bundle(self):
  with TemporaryDirectory() as temp:
   root=Path(temp);template,records=inputs('repeated-payment-breaches-cap');(root/'template.json').write_bytes(template);args=[]
   for index,(key,req,res) in enumerate(records):
    rp=root/(str(index)+'-req.json');sp=root/(str(index)+'-res.json');rp.write_bytes(req);sp.write_bytes(res);args+=['--observation',key,str(rp),str(sp)]
   base=[sys.executable,'-I','-S',str(ROOT/'token_capture.py')];dest=root/'capture';r=subprocess.run([*base,'create','--policy',str(root/'template.json'),'--source-kind','synthetic','--source-note',SOURCE['note'],'--output',str(dest),*args],capture_output=True,timeout=15)
   self.assertEqual(r.returncode,1,r.stderr);self.assertEqual(json.loads(r.stdout)['gate'],1)
   checked=subprocess.run([*base,'check',str(dest)],capture_output=True,timeout=15);self.assertEqual(checked.returncode,1,checked.stderr);self.assertEqual(json.loads(checked.stdout),json.loads(r.stdout))
   bundle=(dest/'payment-bundle.json').read_bytes();self.assertEqual(api['POLICY']['assess_bundle'](bundle),json.loads(checked.stdout)['assessment'])

if __name__=='__main__':unittest.main(verbosity=2)
