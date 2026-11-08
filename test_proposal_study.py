"""Recorded inference replay, byte binding, policy and dishonest-success controls."""
from pathlib import Path
from copy import deepcopy
import json, runpy, shutil, subprocess, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parent
verifier=runpy.run_path(str(ROOT/'tools/verify_proposal_study.py'))
EVIDENCE=verifier['EVIDENCE']
# These original pre-inference controls use labeled fake model responses, never a real model.
StudyControls=runpy.run_path(str(EVIDENCE/'test_study.py'))['StudyControls']

class PackagedStudyTests(unittest.TestCase):
    def test_all_eight_actual_trajectories_replay_without_repair(self):
        result=verifier['verify'](replay=True)
        self.assertTrue(result['verified']);self.assertEqual(len(result['cases']),16)
        self.assertEqual(result['evaluationCallsRecorded'],40);self.assertEqual(result['warmupCallsRecorded'],1)
        metrics=result['metrics']
        self.assertEqual([metrics[k] for k in ['requiredOutputs','passedRequiredOutputs','failedRequiredOutputs','unknownRequiredOutputs']],
                         [16,1,7,8])
        self.assertEqual(metrics['rawOverBudgetBuy'],0);self.assertEqual(metrics['rawRepeatBuyWithJournal'],0)
        self.assertEqual(result['newInferenceCalls'],0);self.assertEqual(result['nativeTransactions'],0)
        self.assertEqual(sum(r['gate']==2 for r in result['cases']),2)
        self.assertEqual(sum(r['gate']==1 for r in result['cases']),14)
    def test_changed_engine_requires_explicit_replay_and_keeps_historical_hashes(self):
        result=verifier['verify'](replay=True)
        self.assertTrue(result['sourceChanged']);self.assertEqual(result['baseCoreVersion'],'0.1.1')
        self.assertEqual(result['coreVersion'],'0.1.2')
        self.assertTrue(all(r['fullReportSha256']!=r['historicalNormalizedReportSha256'] for r in result['cases']))
        command=[sys.executable,'-I','-S',str(ROOT/'tools/verify_proposal_study.py')]
        strict=subprocess.run(command,capture_output=True,timeout=15)
        self.assertEqual(strict.returncode,2);self.assertIn('--replay',json.loads(strict.stdout)['error'])

    def test_changed_input_or_source_is_rejected_before_execution(self):
        for name in ['actual/calls.json','actual/cases.json','actual/execution.json','proposal_oracle.py',
                     'cases/proposal-0-guarded.task.json','cases/proposal-0-guarded.recording.json']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                directory=Path(temp)/'study';shutil.copytree(EVIDENCE,directory)
                path=directory/name;path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaisesRegex(ValueError,'Study evidence changed'):verifier['verify'](directory)
    def test_rewritten_plan_or_rebased_index_cannot_bypass_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'study';shutil.copytree(EVIDENCE,directory)
            path=directory/'study-index.json';index=json.loads(path.read_bytes())
            index['planSha256']='0'*64;path.write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError,'Study index differs'):verifier['verify'](directory)
    def test_separate_reference_rejects_repairs_in_the_actual_capture(self):
        oracle=runpy.run_path(str(EVIDENCE/'proposal_oracle.py'))
        plan=json.loads((EVIDENCE/'locked-plan.json').read_bytes())
        data={name:json.loads((EVIDENCE/'actual'/(name+'.json')).read_bytes()) for name in ['calls','cases','execution']}
        for change in ['answer','context','missing-case','invented-admission','tokens','warmup-id','shutdown']:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                modified=deepcopy(data)
                if change=='answer':modified['cases'][0]['recordedAnswers']['A']['units']+=1
                elif change=='context':modified['calls'][1]['input']['ownerLimitCents']+=1
                elif change=='missing-case':modified['cases'].pop()
                elif change=='invented-admission':modified['cases'][0]['hostEvents'][0]['hostEffect']='new_virtual_payment'
                elif change=='tokens':modified['calls'][1]['tokensGenerated']=True
                elif change=='warmup-id':modified['calls'][0]['id']=1
                elif change=='shutdown':modified['execution']['modelServerStopped']=False
                for name,value in modified.items():(Path(temp)/(name+'.json')).write_text(json.dumps(value))
                with self.assertRaises(ValueError):oracle['check'](plan,Path(temp))
    def test_workbench_examples_preserve_raw_recording_bytes_and_synthetic_origin(self):
        app=runpy.run_path(str(ROOT/'workbench.py'))
        for name,expected in [('proposal-wrong-answer',['failed','unknown']),('proposal-missing-work',['passed','unknown']),
                              ('proposal-independent-b',['unknown','failed'])]:
            scenario=app['CATALOG'][name];self.assertEqual(scenario['kind'],'model-proposals')
            task,sources=app['data_for'](scenario)
            self.assertEqual(json.loads(task)['authority']['kind'],'counterfactual')
            result=app['evaluate'](task,sources)['report']
            self.assertTrue(all(c['status']=='within' for c in result['constraints']))
            self.assertEqual([u['status'] for u in result['utility']['required']],expected)

if __name__=='__main__':unittest.main(verbosity=2)
