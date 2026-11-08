"""Post-discovery development controls; not part of the registered prospective batch."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json,unittest
HERE=Path(__file__).resolve().parent
code=(HERE/'candidate/agent_crash_lab.py').read_bytes();core={'__name__':'union_edges'}
exec(compile(code,'union_candidate','exec'),core)
def pack(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def base(name):
    bundle=json.loads((HERE/'bundles'/(name+'.json')).read_bytes())
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
if __name__=='__main__':unittest.main(verbosity=2)
