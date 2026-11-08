"""Post-discovery development controls; not part of the registered prospective batch."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json,runpy,shutil,tempfile,unittest
HERE=Path(__file__).resolve().parent
verifier=runpy.run_path(str(HERE/'tools/verify_async_study.py'))
REGISTRATION=verifier['checked_registration']()
builder=verifier['constructors']()
reference=runpy.run_path(str(verifier['EVIDENCE']/'sources/async_reference.py'))['reference']
plans={p['id']:p for p in REGISTRATION['plans']}
code=(HERE/'agent_crash_lab.py').read_bytes();core={'__name__':'union_edges'}
exec(compile(code,'union_candidate','exec'),core)
def pack(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def base(name):
    identity,variant=name.rsplit('-',1)
    bundle=builder['bundle'](plans[identity],variant)
    return json.loads(bundle['task_utf8']),{k:v.encode() for k,v in bundle['sources_utf8'].items()}
def run(owner,sources,capture):
    sources={**sources,'recording':pack(capture)};owner['sources']['recording']=sha256(sources['recording']).hexdigest()
    report=core['assess'](pack(owner),sources);assert report['invocation']['status']=='assessed',report
    return report,{r['id']:r for r in report['constraints']}
def views(capture):return [r['response']['result'] for r in capture['rpcObservations'] if r['request']['method']=='tx_status'][:2]
class UnionEdges(unittest.TestCase):
    def test_incompatible_cross_view_parents_fail_closed_without_hiding_B(self):
        owner,sources=base('complementary-final-heads-tight-original');capture=json.loads(sources['recording'])
        common_id='counterfactual-shared-descendant';template=deepcopy(views(capture)[0]['receipts'][-1])
        template['receipt_id']=common_id;template['predecessor_id']=template['receiver_id']
        template['receipt']['Action']['actions']=[{'Transfer':{'deposit':'0'}}]
        common=deepcopy(views(capture)[0]['receipts_outcome'][-1]);common['id']=common_id
        for view in views(capture):
            view['receipts_outcome'][-1]['outcome']['receipt_ids']=[common_id]
            view['receipts_outcome'].append(deepcopy(common));view['receipts'].append(deepcopy(template))
        report,rows=run(owner,sources,capture)
        self.assertEqual(rows['A-merchant']['status'],'conflict');self.assertEqual(rows['A-merchant']['known_subtotal'],'0')
        self.assertEqual(rows['B-merchant']['status'],'within')
        self.assertIn('incompatible_partial_graphs',{d['category'] for d in report['diagnostics']})
    def test_pending_to_final_head_upgrades_once_in_either_order(self):
        for reverse in [False,True]:
            owner,sources=base('same-leaf-repeated-tight-original');capture=json.loads(sources['recording'])
            first,second=views(capture)
            pending=second if reverse else first
            pending['receipts_outcome'][-1]['outcome']['status']='Unknown'
            pending['receipts_outcome'][-1]['block_hash']='counterfactual-pending-block'
            report,rows=run(owner,sources,capture)
            self.assertEqual(rows['A-merchant']['known_subtotal'],'6');self.assertEqual(rows['A-merchant']['status'],'breached')
            self.assertIsNone(rows['A-merchant']['exact_total'])
            fact=next(f for f in report['native_facts'] if f['intent']=='A' and f['to'].startswith('merchant.'))
            self.assertEqual(fact['committed_yocto'],'6');self.assertEqual(fact['execution_state'],'committed')
            self.assertIn('/rpcObservations/'+str(1 if reverse else 2)+'/',fact['outcome_ref']['pointer'])
    def test_body_and_terminal_outcome_may_come_from_different_bound_views(self):
        owner,sources=base('same-leaf-repeated-tight-original');capture=json.loads(sources['recording'])
        first,second=views(capture);del first['receipts']
        second['receipts_outcome'][-1]['outcome']['status']='Unknown'
        second['receipts_outcome'][-1]['block_hash']='counterfactual-pending-block'
        report,rows=run(owner,sources,capture)
        self.assertEqual(rows['A-merchant']['known_subtotal'],'6')
        fact=next(f for f in report['native_facts'] if f['intent']=='A' and f['to'].startswith('merchant.'))
        self.assertIn('/rpcObservations/1/',fact['outcome_ref']['pointer'])
        self.assertIn('/rpcObservations/2/',fact['action_ref']['pointer'])
        self.assertFalse(report['coverage']['financial_scope_complete'])
    def test_wrong_final_head_cannot_finalize_either_partial_leaf(self):
        owner,sources=base('complementary-final-heads-tight-original');capture=json.loads(sources['recording'])
        for row in capture['rpcObservations']:
            if row['request']['method']=='block':row['response']['result']['header']['hash']='unrelated-final-block'
        report,rows=run(owner,sources,capture)
        self.assertEqual(rows['A-merchant']['known_subtotal'],'0');self.assertEqual(rows['A-merchant']['status'],'unknown')
        self.assertEqual(rows['B-merchant']['status'],'within')

class ReferenceControls(unittest.TestCase):
    def test_unique_union_can_prove_excess_without_completeness(self):
        row=reference(plans['complementary-final-heads-tight'])
        self.assertEqual(row['A-merchant'],{'known_subtotal':'8','exact_total':None,'status':'breached'})
        self.assertEqual(row['A-count'],{'known_subtotal':'1','exact_total':None,'status':'unknown'})
        self.assertEqual(row['B-merchant'],{'known_subtotal':'3','exact_total':'3','status':'within'})
    def test_one_or_no_final_anchor_has_only_its_own_lower_bound(self):
        self.assertEqual(reference(plans['single-final-head-tight'])['A-merchant']['known_subtotal'],'6')
        self.assertEqual(reference(plans['no-final-heads-tight'])['A-merchant'],
                         {'known_subtotal':'0','exact_total':None,'status':'unknown'})
    def test_repeated_identity_not_repeated_payment(self):
        self.assertEqual(reference(plans['same-leaf-repeated-tight'])['A-merchant']['known_subtotal'],'6')
        self.assertEqual(reference(plans['same-leaf-repeated-tight'])['A-count']['known_subtotal'],'1')
    def test_zero_and_u128_are_exact_integers(self):
        self.assertEqual(reference(plans['whole-final-zero'])['A-merchant'],
                         {'known_subtotal':'0','exact_total':'0','status':'within'})
        row=reference(plans['complementary-final-heads-u128'])['A-merchant']
        self.assertEqual(row['known_subtotal'],str(2**128));self.assertEqual(row['status'],'breached')
    def test_open_horizon_and_identity_conflict_do_not_pass(self):
        self.assertIsNone(reference(plans['open-horizon-allowed'])['A-merchant']['exact_total'])
        row=reference(plans['conflicting-leaf-tight'])
        self.assertEqual(row['A-merchant']['status'],'conflict');self.assertEqual(row['B-merchant']['status'],'within')

class AsyncPackagingTests(unittest.TestCase):
    def test_registered_failure_reproduces_and_current_engine_matches_all_cases(self):
        result=verifier['verify']()
        self.assertEqual(result['original']['matched'],84);self.assertEqual(result['original']['disagreed'],12)
        self.assertEqual(result['current']['matched'],96);self.assertEqual(result['current']['disagreed'],0)
        self.assertEqual(len(result['previousBaselinesUnchangedExceptVersion']),43)
        self.assertEqual(result['modelCalls'],0);self.assertEqual(result['nativeTransactions'],0)
        by_plan={}
        for row in result['cases']:by_plan.setdefault(row['plan'],[]).append(row['financial'])
        self.assertTrue(all(rows[0]==rows[1]==rows[2] for rows in by_plan.values()))

    def test_changed_registration_or_executable_evidence_fails_before_execution(self):
        for name in ['registration.json','sources/async_reference.py','baseline/agent_crash_lab.py','index.json']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temporary:
                target=Path(temporary)/'study';shutil.copytree(verifier['EVIDENCE'],target)
                path=target/name;path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaises(ValueError):verifier['checked_registration'](target)

    def test_four_deliberate_semantic_defects_are_detected(self):
        changes={
          'restore-largest-view-selection':("g = self.combine_partial_graphs(graphs) if len(graphs) > 1 else candidates[0]",
                                            "g = max(candidates, key=lambda graph: len(graph['bodies']))"),
          'accept-unanchored-partial-effects':("else 'unresolved')","else 'bound_final_head')"),
          'declare-merged-partials-complete':("structural_final=False, issues=issues, expanded=True)",
                                              "structural_final=True, issues=issues, expanded=True)"),
          'ignore-native-identity-conflict':("if not graphs or conflict:","if not graphs:")}
        prior=json.loads((verifier['EVIDENCE']/'initial-candidate-audit.json').read_bytes())
        recorded={r['mutation']:r for r in prior['semanticMutations']}
        for name,(before,after) in changes.items():
            with self.subTest(name=name):
                text=code.decode();self.assertEqual(text.count(before),1)
                mutated=text.replace(before,after,1)
                self.assertEqual(sha256(mutated.encode()).hexdigest(),recorded[name]['sourceSha256'])
                module={'__name__':'controlled_async_mutation'};exec(compile(mutated,name,'exec'),module)
                caught=0
                for plan in REGISTRATION['plans']:
                    for variant in ['original','reversed','duplicated']:
                        report=verifier['assess'](module,builder['bundle'](plan,variant))
                        caught+=verifier['projection'](report)!=reference(plan)
                self.assertEqual(caught,recorded[name]['detectedByBundles']);self.assertGreater(caught,0)

    def test_three_examples_keep_partial_unknown_and_allowed_distinct(self):
        app=runpy.run_path(str(HERE/'workbench.py'))
        for name,status,known,complete in [('async-partial-union','breached','8',False),
                                           ('async-unfinalized','unknown','0',False),
                                           ('async-allowed','within','5',True)]:
            scenario=app['CATALOG'][name]
            self.assertEqual(scenario['kind'],'synthetic-async')
            task,sources=app['data_for'](scenario)
            self.assertEqual(json.loads(task)['authority']['kind'],'counterfactual')
            report=app['core'].assess(task,sources)
            A=next(r for r in report['constraints'] if r['id']=='A-merchant')
            self.assertEqual(A['status'],status);self.assertEqual(A['known_subtotal'],known)
            self.assertEqual(report['coverage']['financial_scope_complete'],complete)
            self.assertTrue(all(row['status']=='passed' for row in report['utility']['required']))

if __name__=='__main__':unittest.main(verbosity=2)
