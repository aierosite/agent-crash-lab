"""Replay actual bounded runtime evidence and constructed transport corruptions.

These are same-author source-informed checks, not an independent accuracy study.
Default tests do not execute a node, contract, model, wallet or public RPC.
"""
from pathlib import Path
from hashlib import sha256
import json,runpy,shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parent
api=runpy.run_path(str(ROOT/'receipt_journal.py'))
DATA=ROOT/'verification/receipt-journal'
SAMPLES=json.loads((DATA/'samples.json').read_bytes())

def texts(sample):return ((ROOT/sample['journal']).read_bytes().decode('utf-8'),(ROOT/sample['policy']).read_bytes().decode('utf-8'))

class NativeJournalTests(unittest.TestCase):
    def test_actual_crash_evidence_and_exact_repeat(self):
        for sample in SAMPLES:
            journal,policy=texts(sample);report=api['assess_bundle'](journal,policy)
            self.assertEqual(report['assessment'],json.loads((ROOT/sample['reference']).read_bytes()))
            self.assertEqual(report['assessment']['required_payment_gate'],sample['expectedGate'])
            self.assertFalse(report['assessment']['whole_run_complete'])
            self.assertEqual((ROOT/sample['journal']).read_bytes(),(ROOT/sample['repeatJournal']).read_bytes())
            self.assertEqual(report['assessor_sha256'],sha256((ROOT/'receipt_journal.py').read_bytes()).hexdigest())
            self.assertEqual(report['math_sha256'],sha256((ROOT/'receipt_journal_math.py').read_bytes()).hexdigest())
            self.assertEqual(report['policy_sha256'],sha256((ROOT/sample['policy']).read_bytes()).hexdigest())

    def test_constructed_transport_and_horizon_controls(self):
        audit=json.loads((DATA/'BOUNDARY-AUDIT.json').read_bytes())
        for row in audit['rows']:
            journal=(DATA/'controls'/(row['name']+'.jsonl')).read_bytes().decode('utf-8');policy=(DATA/'controls'/(row['name']+'.policy.json')).read_bytes().decode('utf-8')
            self.assertEqual(sha256(journal.encode()).hexdigest(),row['rawSha256'])
            if row['expected']=='reject':
                with self.assertRaises(ValueError,msg=row['name']):api['assess_bundle'](journal,policy)
            else:self.assertEqual(api['assess_bundle'](journal,policy)['assessment'],row['corrected']['report'])

    def test_archived_original_false_acceptances_are_reproducible(self):
        archive=DATA/'capture-source';provenance=json.loads((archive/'PROVENANCE.json').read_bytes())
        for name,item in provenance['files'].items():self.assertEqual(sha256((archive/name).read_bytes()).hexdigest(),item['sha256'])
        frozen=runpy.run_path(str(archive/'historical-review.py'));count=0
        for row in json.loads((DATA/'BOUNDARY-AUDIT.json').read_bytes())['rows']:
            if row['expected']!='reject' or not row['original']['accepted']:continue
            raw=(DATA/'controls'/(row['name']+'.jsonl')).read_bytes();policy=(DATA/'controls'/(row['name']+'.policy.json')).read_bytes()
            self.assertEqual(frozen['review'](raw,frozen['load'](policy)),row['original']['report'])
            with self.assertRaises(ValueError,msg=row['name']):api['assess_bundle'](raw.decode(),policy.decode())
            count+=1
        self.assertEqual(count,7)

    def test_unobserved_amount_is_not_zero(self):
        name='before-payment-torn-block-result'
        r=api['assess_bundle']((DATA/'controls'/(name+'.jsonl')).read_bytes().decode('utf-8'),(DATA/'controls'/(name+'.policy.json')).read_bytes().decode('utf-8'))['assessment']
        self.assertEqual(r['required_payment_gate'],2);self.assertEqual(r['root_status'],'unobserved')
        self.assertIsNone(r['principal_received']);self.assertIsNone(r['beneficiary_delta'])

    def test_equivalent_integer_receipt_refund_keeps_canonical_text_output(self):
        journal,policy=texts(SAMPLES[3]);events=[json.loads(line) for line in journal.splitlines()]
        def change(value):
            if type(value) is list:
                for item in value:change(item)
            elif type(value) is dict:
                if set(value)=={'Transfer'} and value['Transfer'].get('deposit')=='100':value['Transfer']['deposit']=100
                for item in value.values():change(item)
        change(events)
        mutated=''.join(json.dumps(e,separators=(',',':'))+'\n' for e in events)
        original=api['assess_bundle'](journal,policy);result=api['assess_bundle'](mutated,policy)
        self.assertEqual(original['assessment'],result['assessment'])
        self.assertEqual(result['assessment']['principal_refunds'][0]['amount'],'100')
        self.assertNotEqual(original['journal_sha256'],result['journal_sha256'])

    def test_exact_raw_text_binding_is_separate_from_semantics(self):
        journal,policy=texts(SAMPLES[1]);one=api['assess_bundle'](journal,policy);two=api['assess_bundle'](journal,policy+'\n')
        self.assertEqual(one['assessment'],two['assessment'])
        self.assertNotEqual(one['policy_sha256'],two['policy_sha256'])
        self.assertEqual(one['journal_sha256'],sha256(journal.encode('utf-8')).hexdigest())
        self.assertEqual(two['policy_sha256'],sha256((policy+'\n').encode('utf-8')).hexdigest())

    def test_loaded_code_does_not_claim_a_later_file_fingerprint(self):
        with tempfile.TemporaryDirectory(prefix='crash-lab-loaded-source-') as folder:
            temp=Path(folder)
            for name in ['receipt_journal.py','receipt_journal_math.py']:shutil.copyfile(ROOT/name,temp/name)
            loaded=runpy.run_path(str(temp/'receipt_journal.py'));journal,policy=texts(SAMPLES[1]);first=loaded['assess_bundle'](journal,policy)
            for name in ['receipt_journal.py','receipt_journal_math.py']:
                path=temp/name;path.write_bytes(path.read_bytes()+b'\n# Controlled hot-deployment fingerprint check.\n')
            old=loaded['assess_bundle'](journal,policy)
            self.assertEqual(first,old)
            self.assertNotEqual(old['assessor_sha256'],sha256((temp/'receipt_journal.py').read_bytes()).hexdigest())
            fresh=runpy.run_path(str(temp/'receipt_journal.py'))['assess_bundle'](journal,policy)
            self.assertNotEqual(old['assessor_sha256'],fresh['assessor_sha256'])
            self.assertEqual(old['assessment'],fresh['assessment'])

    def test_cli_report_success_and_explicit_gate(self):
        for sample in SAMPLES:
            common=[sys.executable,'-I','-S',str(ROOT/'receipt_journal.py'),'--journal',str(ROOT/sample['journal']),'--policy',str(ROOT/sample['policy'])]
            for gate in [False,True]:
                r=subprocess.run(common+(['--gate'] if gate else []),cwd=ROOT,capture_output=True,timeout=15)
                self.assertEqual(r.returncode,sample['expectedGate'] if gate else 0)
                self.assertEqual(r.stderr,b'');self.assertEqual(json.loads(r.stdout),api['assess_bundle'](*texts(sample)))
        r=subprocess.run([sys.executable,'-I','-S',str(ROOT/'receipt_journal.py'),'--journal',str(DATA/'controls/boolean-success.jsonl'),'--policy',str(DATA/'controls/boolean-success.policy.json')],cwd=ROOT,capture_output=True,timeout=15)
        self.assertEqual(r.returncode,2);self.assertEqual(r.stderr,b'')
        self.assertTrue(json.loads(r.stdout)['rejected']);self.assertIn('Base64',json.loads(r.stdout)['error'])

if __name__=='__main__':unittest.main()
