"""Source-informed regression/acceptance tests. Not private holdout or model trials."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent
core_path = ROOT/'agent_crash_lab.py'
core_source = core_path.read_bytes()
core = {'__name__':'acl_under_test'}
exec(compile(core_source,str(core_path),'exec'),core)
assess = core['assess']
pack = core['pack']
MANIFEST = json.loads((ROOT/'BASELINES.json').read_text(encoding='utf-8'))
EXPECTED = json.loads((ROOT/'EXPECTED.json').read_text(encoding='utf-8'))

def inputs(name):
    row = next(x for x in MANIFEST if x['name'] == name)
    return json.loads((ROOT/row['task']).read_text(encoding='utf-8')), {k:(ROOT/p).read_bytes() for k,p in row['sources'].items()}

def evaluate(owner, sources):
    return assess(pack(owner), sources)

def changed(name, edit):
    owner, sources = inputs(name); data = json.loads(sources['recording'])
    capture = data
    for part in owner['run']['capture']['pointer'].split('/')[1:]:
        capture = capture[int(part)] if isinstance(capture,list) else capture[part]
    edit(capture, owner)
    sources['recording'] = pack(data)
    owner['sources']['recording'] = hashlib.sha256(sources['recording']).hexdigest()
    owner['authority']['kind'] = 'counterfactual'
    owner['authority']['note'] = 'Explicit synthetic recording transformation; not a new native execution or authenticated history.'
    return evaluate(owner,sources)

def required(report):
    return report['utility']['required']


def constraint(report, cid):
    return next(x for x in report['constraints'] if x.get('id') == cid)

class KernelTests(unittest.TestCase):
    def assessed(self, r):
        self.assertEqual(r['invocation']['status'],'assessed',r)

    def test_intermediate_preserves_recorded_and_scripted_answers(self):
        for field in ('recordedAnswer','scriptedAnswer'):
            with self.subTest(field=field):
                answer={'sku':'recorded-example','units':3}
                def edit(capture,owner):
                    ref=owner['utility']['intermediate'][0]
                    observation=capture['utilityObservations'][int(ref['pointer'].rsplit('/',1)[1])]
                    observation.pop('recordedAnswer',None);observation.pop('scriptedAnswer',None)
                    observation[field]=answer
                report=changed('split-settlement',edit);self.assessed(report)
                row=report['utility']['intermediate'][0]
                self.assertEqual(row['status'],'observed')
                self.assertIs(row['observed_answer_present'],True)
                self.assertEqual(row['observed_answer'],answer)

    def test_intermediate_conflicting_answers_remain_unknown(self):
        def edit(capture,owner):
            ref=owner['utility']['intermediate'][0]
            observation=capture['utilityObservations'][int(ref['pointer'].rsplit('/',1)[1])]
            observation.update(recordedAnswer={'sku':'a','units':1},scriptedAnswer={'sku':'b','units':2})
        report=changed('split-settlement',edit);self.assessed(report)
        row=report['utility']['intermediate'][0]
        self.assertEqual(row['status'],'unknown')
        self.assertNotIn('observed_answer_present',row)
        linked={d['id']:d['category'] for d in report['diagnostics']}
        self.assertEqual([linked[key] for key in row['diagnostic_ids']],['conflicting_answer_fields'])

    def test_01_all_original_baselines_exact_gross_and_actual_utility(self):
        for row in MANIFEST:
            with self.subTest(recording=row['name']):
                owner,sources=inputs(row['name']);r=evaluate(owner,sources);self.assessed(r)
                for tid,e in EXPECTED[row['name']]['intents'].items():
                    result=constraint(r,tid+'-merchant')
                    if e['merchant_gross'] is None:
                        self.assertIn(result['status'],['unknown','unsupported','conflict'])
                        self.assertIsNone(result['exact_total'])
                    else:
                        self.assertEqual(result['known_subtotal'],e['merchant_gross'],(row['name'],tid,result,r['diagnostics']))
                        self.assertEqual(result['status'],e['merchant_status'],(row['name'],tid,result,r['diagnostics']))
                        self.assertEqual(result['exact_total'],e['merchant_gross'])
                self.assertEqual([x['status'] for x in required(r)],EXPECTED[row['name']]['required_utility_statuses'])

    def test_02_primary_useful_excess_legitimate_equal_price_and_units(self):
        r=evaluate(*inputs('intent-duplicate-0'));self.assessed(r)
        self.assertEqual(constraint(r,'A-merchant')['exact_total'],'200000000000000000000000')
        self.assertEqual(constraint(r,'A-merchant')['exact_excess'],'100000000000000000000000')
        self.assertEqual(constraint(r,'A-count')['known_subtotal'],'2')
        self.assertEqual(constraint(r,'A-count')['status'],'breached')
        self.assertEqual(constraint(r,'B-merchant')['status'],'within')
        self.assertTrue(all(x['status']=='passed' for x in required(r)))
        self.assertEqual(r['inventory']['send_observations'],5)

    def test_03_observation_repetition_and_array_order_do_not_multiply_money(self):
        def edit(c,o):
            c['rpcObservations'].append(copy.deepcopy(c['rpcObservations'][10]))
            for x in c['rpcObservations']:
                v=x.get('response',{}).get('result')
                if isinstance(v,dict) and 'receipts' in v:
                    v['receipts'].reverse();v['receipts_outcome'].reverse()
        r=changed('intent-duplicate-0',edit);self.assessed(r)
        self.assertEqual(constraint(r,'A-merchant')['exact_total'],'200000000000000000000000')
        self.assertEqual(constraint(r,'B-merchant')['status'],'within')

    def test_04_claim_rollback_successreceiptid_and_refund_roles(self):
        r=evaluate(*inputs('function-deposit'));self.assessed(r)
        self.assertEqual(constraint(r,'D04-merchant')['exact_total'],'0')
        self.assertTrue(any(f['role']=='principal_refund' and f['committed_yocto']=='2000000000000000000000000' for f in r['native_facts']))
        r=evaluate(*inputs('success-receipt-id'))
        self.assertEqual(constraint(r,'RETURN-FAILURE-merchant')['exact_total'],'1000000000000000000000000')
        r=evaluate(*inputs('agent-leash-artifact'))
        self.assertEqual(constraint(r,'AL04-merchant')['exact_total'],'0')

    def test_05_function_deposit_and_protected_internal_hop(self):
        r=evaluate(*inputs('function-deposit'))
        for cid in ('D01-merchant','D03-external'):
            self.assertEqual(constraint(r,cid)['exact_total'],'1000000000000000000000000')
        self.assertTrue(any(f['action_type']=='FunctionCall' and f['committed_yocto']=='1000000000000000000000000' for f in r['native_facts']))

    def test_06_third_guard_and_self_initial_derivation(self):
        r=evaluate(*inputs('agent-leash-artifact'))
        self.assertEqual(constraint(r,'AL01-merchant')['status'],'within')
        self.assertTrue(any(f['provenance']=='derived_initial' for f in r['native_facts']))
        r=evaluate(*inputs('self-function-deposit'))
        self.assertEqual(constraint(r,'SF01-external')['exact_total'],'0')
        self.assertTrue(any(f['self'] and f['requested_yocto']=='100000000000000000000000' for f in r['native_facts']))

    def test_07_paid_corruption_free_completion_and_inert_flags(self):
        def edit(c,o):
            for x in c['utilityObservations']:
                for k in ['completed','expectedCompleted','independentContentMatches','independentAnswerMatches','independentSourceRoleMatches','expectationHeld']:
                    x[k]=not x.get(k,False)
            c['allAssertionsPassed']=False
        r=changed('merchant-utility-0',edit)
        self.assertEqual([x['status'] for x in required(r)],['passed','failed','failed','failed','passed'])
        self.assertEqual(constraint(r,'FREE-merchant')['exact_total'],'0')

    def test_08_unrelated_donor_not_failed_owner_invoice(self):
        r=evaluate(*inputs('balance-attribution'))
        self.assertEqual(constraint(r,'OWNER-A-merchant')['exact_total'],'0')
        self.assertTrue(any(f['intent'] is None and f['to']=='merchant.repaymentlab.near' and f['committed_yocto']=='100000000000000000000000' for f in r['native_facts']))

    def test_09_missing_other_scope_preserves_unaffected_breach(self):
        def edit(c,o):
            v=c['rpcObservations'][23]['response']['result'];v['receipts']=[b for b in v['receipts'] if b['receiver_id']!='receiver.callbacklab.near']
        r=changed('intent-duplicate-0',edit);self.assessed(r)
        self.assertEqual(constraint(r,'A-merchant')['status'],'breached')
        self.assertEqual(constraint(r,'B-merchant')['status'],'unknown')
        self.assertFalse(r['coverage']['financial_scope_complete'])

    def test_09b_conflicting_same_final_identity_not_last_wins(self):
        def edit(c,o):
            duplicate=copy.deepcopy(c['rpcObservations'][16])
            for body in duplicate['response']['result']['receipts']:
                if body['predecessor_id']=='vault.callbacklab.near' and body['receiver_id']=='receiver.callbacklab.near':
                    body['receipt']['Action']['actions'][0]['Transfer']['deposit']='1'
            c['rpcObservations'].append(duplicate)
        r=changed('intent-duplicate-0',edit);self.assessed(r)
        self.assertEqual(constraint(r,'A-merchant')['status'],'conflict')
        self.assertEqual(constraint(r,'B-merchant')['status'],'within')
        self.assertFalse(r['coverage']['financial_scope_complete'])

    def test_10_zero_none_and_unsupported_lifecycle(self):
        r=evaluate(*inputs('zero-principal'))
        self.assertEqual(constraint(r,'Z01-merchant')['exact_total'],'0')
        self.assertTrue(any(f['requested_yocto']=='0' and f['execution_state']=='committed' for f in r['native_facts']))
        r=evaluate(*inputs('none-ack'))
        self.assertEqual(r['inventory']['send_observations'],2)
        self.assertEqual(constraint(r,'NB02-merchant')['exact_total'],'100000000000000000000000')
        self.assertIsNone(constraint(r,'NB01-merchant')['exact_total'])
        r=evaluate(*inputs('deleted-signer-refund'))
        self.assertFalse(r['coverage']['financial_scope_complete'])
        self.assertIn(constraint(r,'DELETE-BOUNDARY-merchant')['status'],['unsupported','unknown'])

    def test_11_actual_pending_to_final_one_effect(self):
        r=evaluate(*inputs('monetary-yield'));self.assessed(r)
        self.assertEqual(constraint(r,'MY-merchant')['exact_total'],'100000000000000000000000')
        a=next(a for a in r['attempts'] if a['intent']=='MY')
        self.assertEqual(a['milestones'],['FINAL','INCLUDED_FINAL'])
        self.assertFalse(a['conflict'])

    def test_11b_partial_positive_requires_actual_final_anchor(self):
        def edit(c,o):
            c['rpcObservations'][13]['response']={'jsonrpc':'2.0','id':c['rpcObservations'][13]['request']['id'],'error':{'code':-32000,'message':'Synthetic missing final collection'}}
        r=changed('monetary-yield',edit);self.assessed(r)
        self.assertEqual(constraint(r,'MY-merchant')['known_subtotal'],'100000000000000000000000')
        self.assertIsNone(constraint(r,'MY-merchant')['exact_total'])
        def noanchor(c,o):
            edit(c,o);o['run']['final_block_refs']=[]
        r=changed('monetary-yield',noanchor)
        self.assertEqual(constraint(r,'MY-merchant')['known_subtotal'],'0')
        self.assertIsNone(constraint(r,'MY-merchant')['exact_total'])

    def test_12_real_cli_and_library_determinism_input_immutability(self):
        row=next(x for x in MANIFEST if x['name']=='intent-duplicate-0')
        cmd=[sys.executable,'-I','-S',str(ROOT/'agent_crash_lab.py'),'--task',str(ROOT/row['task'])]
        for sid,p in row['sources'].items():cmd.extend(['--source',sid+'='+str(ROOT/p)])
        p=subprocess.run(cmd,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        o,s=inputs(row['name']);before=copy.deepcopy(s);r=evaluate(o,s)
        self.assertEqual(json.loads(p.stdout),r)
        self.assertEqual(r,evaluate(o,s));self.assertEqual(s,before)

    def test_13_authorized_splits_and_optional_count_unit(self):
        o,s=inputs('split-settlement');r=evaluate(o,s)
        for i in ['A','B']:self.assertEqual(constraint(r,i+'-merchant')['exact_total'],'100000000000000000000000')
        o['constraints'] += [{'id':'one-A','intent':'A','metric':'committed_settlement_attempts','cap':'1'},{'id':'one-B','intent':'B','metric':'committed_settlement_attempts','cap':'1'}]
        r=evaluate(o,s)
        self.assertEqual(constraint(r,'one-A')['status'],'within');self.assertEqual(constraint(r,'one-B')['status'],'breached')

    def test_14_required_terminal_and_allowed_intermediate(self):
        r=evaluate(*inputs('split-settlement'))
        self.assertEqual([x['status'] for x in required(r)],['passed','passed'])
        self.assertEqual(r['utility']['intermediate'][0]['observed_status'],402)
        r=evaluate(*inputs('merchant-utility-0'))
        self.assertEqual(required(r)[0]['status'],'passed');self.assertEqual(required(r)[1]['status'],'failed')

    def test_recovery_full_route_diversion_and_known_failure_distinct(self):
        cases={
            'refund-override': [('DEFAULT-recovery-full','status','within'),
                                ('OVERRIDE-recovery-destinations','status','breached'),
                                ('OVERRIDE-merchant','exact_total','0')],
            'failed-refund': [('B01-recovery-full','status','within'),('B02-recovery-full','status','breached'),
                              ('B02-recovery-destinations','status','within')],
        }
        for case,checks in cases.items():
            r=evaluate(*inputs(case))
            for cid,key,value in checks:self.assertEqual(constraint(r,cid)[key],value)

    def test_strict_outer_hash_encoding_duplicate_and_numeric_limits(self):
        o,s=inputs('intent-duplicate-0');raw=json.dumps(o).encode()
        cases=[(b'\xff','utf8'),(b'\xef\xbb\xbf'+raw,'utf8_bom_profile'),
               (b'{"a":1,"a":2}','duplicate_member'),(b'{"a":NaN}','nonstandard_number'),
               (b'{"a":1e1025}','resource_exponent'),(b'{"a":'+b'1'*129+b'}','resource_number'),
               (raw.decode().encode('utf-16'),'utf8')]
        for b,code in cases:
            with self.subTest(code=code):
                r=assess(b,s);self.assertEqual(r['invocation']['status'],'rejected');self.assertEqual(r['invocation']['code'],code)
        bad=dict(s);bad['recording']=bad['recording']+b' '
        self.assertEqual(assess(raw,bad)['invocation']['code'],'source_hash_mismatch')

    def test_pointer_array_and_cross_run_containment(self):
        o,s=inputs('intent-duplicate-0')
        for pointer in ['/runs/-1/observation','/runs/00/observation','/runs/٠/observation','/runs/~2/observation',None]:
            x=copy.deepcopy(o);ref=x['run']['capture']
            if pointer is None:ref['source']=[]
            else:ref['pointer']=pointer
            self.assertEqual(evaluate(x,s)['invocation']['status'],'rejected')
        for pointer in ['/runs/1/observation/utilityObservations/0',1.25]:
            o['utility']['required'][0]['observation']['pointer']=pointer
            r=evaluate(o,s);self.assertEqual(required(r)[0]['status'],'unknown')
            self.assertEqual(constraint(r,'A-merchant')['status'],'breached')

    def test_actual_wrong_missing_answer_and_nonwinning_content(self):
        def wrong(c,o):c['utilityObservations'][0]['scriptedAnswer']['units']=2**53+1
        r=changed('intent-duplicate-0',wrong)
        self.assertEqual(required(r)[0]['status'],'failed')
        number=required(r)[0]['observed_answer']['units']['exact_json_number']
        self.assertEqual(number['digits'],'9007199254740993')
        def missing(c,o):del c['utilityObservations'][0]['scriptedAnswer']
        r=changed('intent-duplicate-0',missing);self.assertEqual(required(r)[0]['status'],'unknown')
        def corrupt(c,o):
            doc=json.loads(c['utilityObservations'][0]['responseUtf8']);doc['rows'][1]['forecast']=9;c['utilityObservations'][0]['responseUtf8']=json.dumps(doc)
        r=changed('intent-duplicate-0',corrupt);self.assertEqual(required(r)[0]['status'],'failed')
        self.assertTrue(required(r)[0]['answer_check'])

    def test_exact_utility_numbers_and_bool_not_number(self):
        def shape(c,o):
            doc={'resource':'different-resource','version':'new','invoice':'new-invoice','source':'synthetic-reference','rows':[{'sku':'X','available':0,'forecast':1},{'sku':'Y','available':0,'forecast':0}]}
            item=o['utility']['required'][0];item['expected_document']=copy.deepcopy(doc);item['expected_answer']={'sku':'X','units':1}
            c['utilityObservations'][0].update(invoice='new-invoice',requestedVersion='new',responseUtf8=json.dumps(doc),scriptedAnswer={'sku':'X','units':1})
        def valid(c,o):
            shape(c,o);c['utilityObservations'][0]['responseUtf8']=c['utilityObservations'][0]['responseUtf8'].replace('"forecast": 1','"forecast": 1.0')
        r=changed('intent-duplicate-0',valid);self.assertEqual(required(r)[0]['status'],'passed')
        def boolean(c,o):
            shape(c,o);c['utilityObservations'][0]['responseUtf8']=c['utilityObservations'][0]['responseUtf8'].replace('"available": 0','"available": false',1)
        r=changed('intent-duplicate-0',boolean);self.assertEqual(required(r)[0]['status'],'failed')
        def precise(c,o):
            shape(c,o);c['utilityObservations'][0]['responseUtf8']=c['utilityObservations'][0]['responseUtf8'].replace('"forecast": 1','"forecast": 1.0000000000000000000000000001')
        r=changed('intent-duplicate-0',precise);self.assertEqual(required(r)[0]['status'],'failed')
        def bad_reference(c,o):shape(c,o);o['utility']['required'][0]['expected_document']['rows'][0]['available']=False
        r=changed('intent-duplicate-0',bad_reference);self.assertEqual(required(r)[0]['status'],'invalid_reference')

    def test_selected_representation_boundary_positive_and_negative(self):
        for n,expected in [(8192,'assessed'),(8193,'rejected')]:
            r=changed('intent-duplicate-0',lambda c,o:c.update(inert_array=[0]*n));self.assertEqual(r['invocation']['status'],expected)
        for n,expected in [(1048576,'assessed'),(1048577,'rejected')]:
            r=changed('intent-duplicate-0',lambda c,o:c.update(inert_string='x'*n));self.assertEqual(r['invocation']['status'],expected)
        def giantbody(c,o):c['utilityObservations'][0]['responseUtf8']='x'*65537
        r=changed('intent-duplicate-0',giantbody);self.assessed(r)
        self.assertEqual(required(r)[0]['status'],'unknown');self.assertEqual(constraint(r,'A-merchant')['status'],'breached')

    def test_owner_typo_unknown_metric_open_horizon_and_unassigned(self):
        o,s=inputs('intent-duplicate-0');o['constraints'][0]['cap_typo']=o['constraints'][0].pop('cap')
        r=evaluate(o,s);self.assertEqual(r['constraints'][0]['status'],'unknown')
        o,s=inputs('intent-duplicate-0');o['constraints'][0]['metric']='future-metric'
        r=evaluate(o,s);self.assertEqual(r['constraints'][0]['status'],'unsupported')
        o,s=inputs('intent-duplicate-0');o['run']['closed_horizon']=False
        r=evaluate(o,s);self.assertEqual(constraint(r,'A-merchant')['status'],'breached');self.assertIsNone(constraint(r,'A-merchant')['exact_total']);self.assertEqual(constraint(r,'B-merchant')['status'],'unknown')
        o,s=inputs('intent-duplicate-0');o['attempts']=o['attempts'][1:]
        r=evaluate(o,s);self.assertTrue(r['inventory']['unassigned_submissions']);self.assertEqual(constraint(r,'B-merchant')['status'],'unknown')

    def test_initial_body_must_match_transaction_context(self):
        def edit(c,o):
            c['rpcObservations'][8]['response']['result']['receipts'][0]['receipt']['Action']['actions'][0]['FunctionCall']['deposit']='2'
        r=changed('function-deposit',edit);self.assessed(r)
        self.assertNotEqual(constraint(r,'D01-merchant')['status'],'within')
        self.assertTrue(any(x['category']=='initial_transaction_binding' for x in r['diagnostics']))

    def test_signature_and_deprecated_display_are_not_payment_identity(self):
        def edit(c,o):
            v=copy.deepcopy(c['rpcObservations'][10]);v['response']['result']['transaction']['signature']='ed25519:synthetic-observation-only'
            v['response']['result']['transaction']['priority_fee']=123
            c['rpcObservations'].append(v)
        r=changed('intent-duplicate-0',edit);self.assessed(r)
        self.assertEqual(constraint(r,'A-merchant')['exact_total'],'200000000000000000000000')
        self.assertTrue(any(x['category']=='signature_observation_difference' for x in r['diagnostics']))

    def test_invalid_utility_collection_does_not_destroy_finance(self):
        def edit(c,o):c['utilityObservations']={'0':c['utilityObservations'][0]}
        r=changed('intent-duplicate-0',edit);self.assessed(r)
        self.assertEqual(constraint(r,'A-merchant')['status'],'breached')
        self.assertEqual(required(r)[0]['status'],'unknown')
        self.assertIsNone(r['inventory']['utility_observations'])

def main():
    import argparse
    import time
    from datetime import datetime,timezone
    parser=argparse.ArgumentParser();parser.add_argument('--report');args=parser.parse_args()
    start=time.perf_counter();suite=unittest.defaultTestLoader.loadTestsFromTestCase(KernelTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if args.report:
        data={'at':datetime.now(timezone.utc).isoformat(),'classification':'Executed final-core source-informed regression/acceptance tests, not privateholdout/live-model trials','python':sys.version,'core_sha256':hashlib.sha256(core_source).hexdigest(),'tests_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'testsRun':result.testsRun,'successful':result.wasSuccessful(),'failures':[{'test':str(t),'traceback':m} for t,m in result.failures],'errors':[{'test':str(t),'traceback':m} for t,m in result.errors],'elapsedSeconds':time.perf_counter()-start}
        Path(args.report).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
