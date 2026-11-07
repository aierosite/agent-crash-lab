"""Research acceptance tests with independent hand-calculated controls."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from datetime import datetime,timezone
from types import SimpleNamespace
import json,runpy,subprocess,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parent
labcode=SimpleNamespace(**runpy.run_path(str(ROOT/'tools/scenario_lab.py')))
oracle=labcode.oracle

def manual():
    intents=[]
    for tid in ['A','B']:
        intents.append({'id':tid,'cap':'5','settlement_cap':'1','fault':'correct',
            'document':{'resource':'inventory','version':'v1','invoice':tid,'source':'hand-written control',
                'rows':[{'sku':'first','available':2,'forecast':5},{'sku':'tied','available':0,'forecast':3}]}})
    return {'format':oracle.FORMAT,'seed':0,'case':0,'intents':intents,
        'transactions':[{'id':'A-split','intent':'A','amounts':['2','3']},{'id':'B-independent','intent':'B','amounts':['5']}]}

class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lab=labcode.Lab()

    def test_manual_equal_price_and_actions_vs_transactions(self):
        plan=manual();expected=oracle.reference(plan)
        self.assertEqual(oracle.solve(plan['intents'][0]['document']),{'sku':'first','units':3})
        self.assertEqual(expected['constraints'],{
            'A-merchant':{'exact_total':'5','status':'within'},'A-count':{'exact_total':'1','status':'within'},
            'B-merchant':{'exact_total':'5','status':'within'},'B-count':{'exact_total':'1','status':'within'}})
        result=self.lab.run(plan);self.assertTrue(result['matches']);self.assertEqual(result['actual']['gate'],0)
        second=deepcopy(plan);second['transactions'][0]['amounts']=['2']
        second['transactions'].append({'id':'A-second','intent':'A','amounts':['3']})
        result=self.lab.run(second);self.assertTrue(result['matches'])
        self.assertEqual(result['actual']['constraints']['A-merchant']['status'],'within')
        self.assertEqual(result['actual']['constraints']['A-count'],{'exact_total':'2','status':'breached'})

    def test_zero_free_work_and_u128_aggregate(self):
        for amounts in [[],['0'],[str(2**128-1)]*4]:
            with self.subTest(amounts=amounts):
                plan=manual();plan['transactions']=[{'id':'edge','intent':'A','amounts':amounts}] if amounts else []
                plan['intents'][0]['cap']=str(sum(map(int,amounts)))
                result=self.lab.run(plan);self.assertTrue(result['matches'])
                self.assertEqual(result['actual']['gate'],0)
                self.assertTrue(all(s=='passed' for s in result['actual']['utility'].values()))

    def test_each_output_fault_does_not_invent_a_payment_breach(self):
        for fault,expected in [('correct','passed'),('wrong_answer','failed'),('wrong_document','failed'),
                               ('missing_answer','unknown'),('http_denied','failed')]:
            with self.subTest(fault=fault):
                plan=manual();plan['intents'][1]['fault']=fault;result=self.lab.run(plan)
                self.assertTrue(result['matches'])
                self.assertEqual(result['actual']['utility']['B-output'],expected)
                self.assertTrue(all(c['status']=='within' for c in result['actual']['constraints'].values()))

    def test_seeded_generation_is_deterministic_structurally_varied_and_agrees(self):
        signatures=set();counts={0:0,1:0,2:0};examples=0
        for seed in [0,1,42,2**32-1]:
            for index in range(32):
                plan=labcode.generate(seed,index);before=oracle.canonical(plan)
                self.assertEqual(plan,labcode.generate(seed,index))
                result=self.lab.run(plan);self.assertTrue(result['matches'],(seed,index,result['actual'],result['expected']))
                self.assertEqual(before,oracle.canonical(plan),'Lab mutated its input')
                signatures.add(tuple((tx['intent'],len(tx['amounts'])) for tx in plan['transactions']))
                counts[result['actual']['gate']]+=1;examples+=1
        self.assertGreater(len(signatures),50);self.assertTrue(all(counts.values()))
        self.generated={'cases':examples,'structuralShapes':len(signatures),'gates':counts}
        type(self).generation=self.generated

    def test_financial_reduction_preserves_authority_and_correct_work(self):
        plan=labcode.generate(42,1);frozen=deepcopy(plan)
        self.assertGreater(int(plan['intents'][0]['cap']),0)
        result=labcode.shrink(self.lab,plan)
        reduced=result['reduced'];self.assertEqual(plan,frozen)
        self.assertEqual(reduced['blueprint']['intents'],plan['intents'])
        self.assertEqual(result['predicate'],'constraint:A-merchant')
        self.assertEqual(result['after']['transactions'],1);self.assertEqual(result['after']['actions'],1)
        cap=int(plan['intents'][0]['cap'])
        self.assertEqual(int(reduced['actual']['constraints']['A-merchant']['exact_total']),cap+1)
        self.assertTrue(all(s=='passed' for s in reduced['actual']['utility'].values()))
        self.assertTrue(result['deletionMinimal']);self.assertFalse(result['budgetExhausted'])

    def test_output_reduction_preserves_a_real_positive_synthetic_payment(self):
        plan=manual();plan['intents'][1]['fault']='wrong_document'
        result=labcode.shrink(self.lab,plan);reduced=result['reduced']
        self.assertEqual(result['predicate'],'utility:B-output')
        self.assertEqual(reduced['blueprint']['intents'],plan['intents'])
        self.assertGreater(int(reduced['actual']['constraints']['B-merchant']['exact_total']),0)
        self.assertTrue(all(c['status']=='within' for c in reduced['actual']['constraints'].values()))
        self.assertEqual(reduced['actual']['utility']['A-output'],'passed')

    def test_small_budget_does_not_certify_minimality(self):
        result=labcode.shrink(self.lab,labcode.generate(42,1),budget=1)
        self.assertEqual(result['assessments'],1);self.assertTrue(result['budgetExhausted'])
        self.assertIsNone(result['deletionMinimal']);self.assertTrue(result['reduced']['matches'])

    def test_evaluator_disagreement_aborts_reduction(self):
        class Broken:
            calls=0
            def run(inner,plan):
                inner.calls+=1;result=self.lab.run(plan)
                if inner.calls>1:result['matches']=False
                return result
        with self.assertRaisesRegex(ValueError,'disagreement'):
            labcode.shrink(Broken(),labcode.generate(42,1))

    def test_binding_cannot_mix_a_blueprint_with_another_bundle(self):
        plan=manual();bundle=self.lab.bundle(plan)
        changed=deepcopy(plan);changed['intents'][0]['cap']='0'
        with self.assertRaisesRegex(ValueError,'binding mismatch'):self.lab.evaluate(changed,bundle)

    def test_unicode_byte_bounds_match_the_inventory_reference(self):
        for field in ['resource','version','invoice','source']:
            for value in ['a'*129,'a'*256,'é'*128,'🚀'*64]:
                with self.subTest(field=field,bytes=len(value.encode())):
                    plan=manual();plan['intents'][0]['document'][field]=value
                    result=self.lab.run(plan);self.assertTrue(result['matches']);self.assertEqual(result['actual']['gate'],0)
            for value in ['a'*257,'é'*129,'🚀'*65,'\ud800']:
                plan=manual();plan['intents'][0]['document'][field]=value
                with self.assertRaisesRegex(ValueError,'UTF-8 bytes'):oracle.validate(plan)
        for value in ['é'*64,'🚀'*32]:
            plan=manual();plan['intents'][0]['document']['rows'][0]['sku']=value
            self.assertTrue(self.lab.run(plan)['matches'])
        for value in ['é'*65,'🚀'*33,'\ud800']:
            plan=manual();plan['intents'][0]['document']['rows'][0]['sku']=value
            with self.assertRaisesRegex(ValueError,'UTF-8 bytes'):oracle.validate(plan)

    def test_reproducible_evaluation_detects_planned_faults_and_preserves_sources(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            output=Path(folder)/'evaluation'
            run=subprocess.run([sys.executable,'-I','-S',str(ROOT/'tools/evaluate_suite.py'),'--out',str(output)],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=40)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            record=json.loads((output/'results.json').read_bytes())
            self.assertEqual(record['totals']['generatedMatches'],192)
            self.assertEqual(record['totals']['controlsPassed'],11)
            self.assertEqual(record['totals']['mutationsDetected'],9)
            self.assertEqual(record['totals']['domainDisagreements'],0)
            self.assertTrue(record['sourceIntegrityVerifiedAfter'])
            marker=output/'results.json';before=marker.read_bytes()
            repeated=subprocess.run([sys.executable,'-I','-S',str(ROOT/'tools/evaluate_suite.py'),'--out',str(output)],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=5)
            self.assertEqual(repeated.returncode,2);self.assertEqual(marker.read_bytes(),before)

    def test_interactive_deadline_does_not_certify_a_partial_run(self):
        from unittest.mock import patch
        clock=iter([0,16])
        with patch.dict(labcode.interactive.__globals__,{'time':SimpleNamespace(monotonic=lambda:next(clock))}):
            with self.assertRaisesRegex(ValueError,'time limit'):
                labcode.interactive('search',{'seed':42,'cases':1},self.lab.app)
        from subprocess import TimeoutExpired
        with patch.dict(labcode.interactive.__globals__,{'Lab':lambda **kwargs:SimpleNamespace(
            run=lambda plan:(_ for _ in ()).throw(TimeoutExpired('oracle',5)),
            oracle_mode='isolated-python-process',provenance={})}):
            with self.assertRaisesRegex(ValueError,'five seconds'):
                labcode.interactive('search',{'seed':42,'cases':1},self.lab.app)

    def test_parser_and_domain_bounds(self):
        values=[True,None,-1,2**32]
        for seed in values:
            with self.assertRaises(ValueError):labcode.generate(seed,0)
        for path,value in [('cap','01'),('cap',str(2**256)),('settlement_cap','-1')]:
            plan=manual();plan['intents'][0][path]=value
            with self.assertRaises(ValueError):oracle.validate(plan)
        for amounts in [[],['1']*5,[str(2**128)],['-1'],[True]]:
            plan=manual();plan['transactions'][0]['amounts']=amounts
            with self.assertRaises(ValueError):oracle.validate(plan)
        for bad in [b'{',b'{"format":1,"format":2}',b'{"seed":NaN}',b' '*262145]:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                path=Path(folder)/'bad.json';path.write_bytes(bad)
                with self.assertRaises(ValueError):labcode.load_plan(path)

    def cli(self,*args):
        return subprocess.run([sys.executable,'-I','-S',str(ROOT/'tools/scenario_lab.py'),*map(str,args)],
            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)

    def test_cli_search_replay_exact_bytes_and_existing_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            base=Path(folder);output=base/'nested'/'search'
            run=self.cli('search','--seed',42,'--cases',4,'--out',output)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            summary=json.loads(run.stdout);self.assertEqual(summary['matches'],4)
            self.assertEqual(summary['gates'],{'0':1,'1':2,'2':1})
            files={str(f.relative_to(output)):f.read_bytes() for f in output.rglob('*') if f.is_file()}
            again=self.cli('search','--seed',42,'--cases',4,'--out',output)
            self.assertEqual(again.returncode,2)
            self.assertEqual(files,{str(f.relative_to(output)):f.read_bytes() for f in output.rglob('*') if f.is_file()})
            case=output/'case-1';bundle=case/'bundle.json'
            original=b'\xef\xbb\xbf'+json.dumps(json.loads(bundle.read_bytes()),indent=2).replace('\n','\r\n').encode()
            # A separate original envelope proves replay is not just regeneration.
            unusual=base/'unusual-envelope.json';unusual.write_bytes(original)
            replay=base/'replay'
            run=self.cli('replay','--blueprint',case/'blueprint.json','--bundle',unusual,'--out',replay)
            self.assertEqual(run.returncode,1,run.stdout+run.stderr)
            self.assertEqual(original,(replay/'case-0/bundle.json').read_bytes())
            self.assertEqual(json.loads((replay/'replayed-input.json').read_bytes())['sha256'],sha256(original).hexdigest())
            self.assertTrue(json.loads((replay/'case-0/comparison.json').read_bytes())['matches'])
            self.assertEqual(json.loads((case/'report.json').read_bytes())['report'],
                             json.loads((replay/'case-0/report.json').read_bytes())['report'])

    def test_cli_invalid_bundle_has_no_traceback_or_complete_summary(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            base=Path(folder);plan=base/'plan.json';plan.write_bytes(oracle.canonical(manual()))
            for index,value in enumerate([{},[],None,{'task_utf8':'{}'}]):
                bundle=base/('bad-'+str(index)+'.json');bundle.write_text(json.dumps(value))
                output=base/('out-'+str(index))
                run=self.cli('replay','--blueprint',plan,'--bundle',bundle,'--out',output)
                self.assertEqual(run.returncode,2,run.stderr)
                self.assertNotIn('Traceback',run.stderr);self.assertFalse((output/'summary.json').exists())
                failure=json.loads((output/'failure.json').read_bytes())
                self.assertEqual(failure['state'],'incomplete')
                self.assertIn('generated bundle-v1',failure['error'])

    def test_invalid_provenance_has_an_actionable_error_before_assessment(self):
        plan=manual()
        for changed in [None,{},'not JSON',json.dumps([]),json.dumps({'provenance':None})]:
            with self.subTest(notes=changed):
                bundle=self.lab.bundle(plan);owner=json.loads(bundle['task_utf8'])
                owner['notes']=changed;bundle['task_utf8']=json.dumps(owner)
                with self.assertRaisesRegex(ValueError,'provenance'):
                    self.lab.evaluate(plan,bundle)

    def test_bundled_example_matches_sources_and_keeps_the_same_predicate(self):
        directory=ROOT/'evidence/scenario-lab'
        record=json.loads((ROOT/'verification/scenario-lab.json').read_bytes())
        for name,expected in record['artifacts'].items():
            raw=(ROOT/name).read_bytes()
            self.assertEqual({'bytes':len(raw),'sha256':sha256(raw).hexdigest()},expected,name)
        for name,path in [('scenario_lab.py',ROOT/'tools/scenario_lab.py'),('episode_oracle.py',ROOT/'episode_oracle.py')]:
            self.assertEqual(record['sourceHashes'][name],sha256(path.read_bytes()).hexdigest())
        plans=[]
        for variant in ['original','reduced']:
            plan=labcode.load_plan(directory/(variant+'-blueprint.json'));plans.append(plan)
            bundle=json.loads((directory/(variant+'-bundle.json')).read_bytes())
            result=self.lab.evaluate(plan,bundle);self.assertTrue(result['matches'])
            self.assertEqual(result['actual']['constraints']['A-merchant']['status'],'breached')
            self.assertTrue(all(status=='passed' for status in result['actual']['utility'].values()))
            self.assertEqual(result['response']['report'],json.loads(
                (ROOT/'verification'/('scenario-lab-'+variant+'-report.json')).read_bytes())['report'])
        self.assertEqual(plans[0]['intents'],plans[1]['intents'])
        self.assertEqual(record['reduction']['after'],{'transactions':1,'actions':1,'totalYocto':'5'})

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PrototypeTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'atUtc':datetime.now(timezone.utc).isoformat(),'tests':result.testsRun,'successful':result.wasSuccessful(),
        'failures':len(result.failures),'errors':len(result.errors),'generation':getattr(PrototypeTests,'generation',None),
        'classification':labcode.CLASSIFICATION,'sourceHashes':{p.name:sha256(p.read_bytes()).hexdigest()
            for p in [ROOT/'tools/scenario_lab.py',ROOT/'episode_oracle.py',ROOT/'test_scenario_lab.py']}}
    print(json.dumps(record))
    raise SystemExit(not result.wasSuccessful())
