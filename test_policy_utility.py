from pathlib import Path
import copy,runpy,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;api=runpy.run_path(str(ROOT/'tools/verify_policy_utility.py'));D=api['DATA'];load=api['load']
class PolicyUtility(unittest.TestCase):
 def test_registered_whole_source_projection(self):
  with patch('subprocess.Popen',side_effect=AssertionError('No process allowed')),patch('socket.socket',side_effect=AssertionError('No network allowed')):
   r=api['verify']()
  self.assertEqual((r['registeredCases'],r['commonCasesMatched'],r['differentPolicyCasesRetained']),(12,9,3));self.assertEqual(r['newModelCalls']+r['newSdkCalls']+r['newTransactions'],0)
  rows={r['id']:r for r in r['rows']};self.assertFalse(rows['finish-without-bill']['bankUtility']);self.assertTrue(rows['bill-without-finish']['bankUtility']);self.assertFalse(rows['bill-without-finish']['finish'])
 def test_forged_labels_effects_coverage_and_finish_reject(self):
  cases=load(D/'cases.json');observed=load(D/'observations.json');spec=load(D/'registration.json')
  def utility(rows):rows[0]['bank']['externalUtility']=False
  def effect(rows):rows[0]['bank']['effects'][0]['amount']='1'
  def admission(rows):rows[6]['workcell']['decisions'][0]['allowed']=True
  def coverage(rows):rows.pop()
  def finish(rows):rows[8]['finish']=True
  def type_confusion(rows):rows[0]['workcell']['decisions'][0]['allowed']=1
  for mutate in [utility,effect,admission,coverage,finish,type_confusion]:
   with self.subTest(control=mutate.__name__):
    changed=copy.deepcopy(observed);mutate(changed)
    with self.assertRaises(ValueError):api['check_observations'](cases,changed,spec)
if __name__=='__main__':unittest.main()
