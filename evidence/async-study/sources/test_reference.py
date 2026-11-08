from pathlib import Path
import json,runpy,unittest
HERE=Path(__file__).resolve().parent
reference=runpy.run_path(str(HERE/'async_reference.py'))['reference']
plans={p['id']:p for p in json.loads((HERE/'registration.json').read_bytes())['plans']}
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
if __name__=='__main__':unittest.main(verbosity=2)
