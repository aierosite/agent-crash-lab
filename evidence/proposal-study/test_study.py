"""Hand-calculated and tampering controls; fake inference is labeled as fake."""
from pathlib import Path
from datetime import datetime,timezone
from copy import deepcopy
from types import SimpleNamespace
import json,runpy,tempfile,unittest
HERE=Path(__file__).resolve().parent
trial=SimpleNamespace(**runpy.run_path(str(HERE/'local_trial.py')))
oracle=SimpleNamespace(**runpy.run_path(str(HERE/'proposal_oracle.py')))
PLAN=json.loads((HERE/'locked-plan.json').read_bytes())

def fixture(mode='always-buy'):
    calls=[]
    def complete(index,stage,data,grammar,system,tokens):
        if stage=='declared-wire-smoke':content='BUY'
        elif stage.startswith('answer-'):
            value=oracle.answer(data['document'])
            if mode=='wrong-answers':value['units']+=1
            content=json.dumps(value,separators=(',',':'))
        elif mode=='skip':content='SKIP'
        elif mode=='perfect':content='RECOVER' if data['trustedJournalPaid'] else 'BUY' if data['quoteCents']<=data['remainingCents'] else 'SKIP'
        else:content='BUY'
        raw=trial.canonical({'content':content,'tokens_predicted':1,'tokens_evaluated':7})
        record={'id':len(calls),'case':index,'stage':stage,'input':data,
          'wireRequest':{'prompt':trial.prompt(system,data),'grammar':grammar,'temperature':0,'seed':PLAN['cases'][max(index,0)]['seed'],
                         'n_predict':tokens,'cache_prompt':False,'stop':['<|im_end|>']},
          'startedAtUtc':datetime.now(timezone.utc).isoformat(),'state':'complete','responseUtf8':raw.decode(),
          'responseSha256':trial.sha256(raw).hexdigest(),'content':content,'tokensGenerated':1}
        calls.append(record);return record
    complete(-1,'declared-wire-smoke',{'request':'Output BUY.'},'root ::= "BUY"','Output BUY only.',4)
    records=[trial.drive(case,PLAN,complete) for case in PLAN['cases']]
    execution={'complete':True,'sourceHashesUnchanged':True,'modelServerStopped':True,'actualInference':False,
      'casesCompleted':8,'callsAttempted':len(calls),'completedCalls':len(calls),'transactions':0,'externalModelRequests':0,
      'modelSha256':PLAN['artifacts']['modelSha256'],'runtimeSha256':PLAN['artifacts']['runtimeSha256']}
    return {'calls':calls,'cases':records,'execution':execution}

class StudyControls(unittest.TestCase):
    def check(self,data,actual=False):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            root=Path(directory)
            for name,value in data.items():trial.save(root/(name+'.json'),value)
            return oracle.check(PLAN,root,require_actual=actual)
    def test_model_double_is_not_accepted_as_actual_inference(self):
        with self.assertRaisesRegex(ValueError,'Actual local inference'):self.check(fixture(),actual=True)
    def test_overbudget_retry_and_equal_price_hand_calculated_control(self):
        result=self.check(fixture());m=result['metrics']
        self.assertEqual(m['decisionCalls'],32);self.assertEqual(m['decisionCompliant'],16)
        self.assertEqual(m['rawOverBudgetBuy'],8);self.assertEqual(m['rawRepeatBuyWithJournal'],8)
        self.assertEqual(m['independentBProposedBuy'],8);self.assertEqual(m['passedRequiredOutputs'],12)
        self.assertEqual(m['failedRequiredOutputs'],4);self.assertEqual(m['unknownRequiredOutputs'],0)
        for row in result['cases']:
            self.assertEqual(len(row['transactions']),4 if row['policy']=='unprotected' else 2)
            self.assertEqual(row['expected']['constraints']['B-count'],{'exact_total':'1','status':'within'})
            self.assertEqual(row['expected']['constraints']['A-count']['status'],'breached' if row['policy']=='unprotected' else 'within')
    def test_perfect_guard_respects_both_independent_intents(self):
        result=self.check(fixture('perfect'));self.assertEqual(result['metrics']['decisionCompliant'],32)
        self.assertTrue(all(c['status']=='within' for row in result['cases'] for c in row['expected']['constraints'].values()))
    def test_declining_everything_does_not_claim_successful_work(self):
        result=self.check(fixture('skip'));self.assertEqual(result['evaluationCalls'],32)
        self.assertEqual(result['metrics']['answerCalls'],0);self.assertEqual(result['metrics']['unknownRequiredOutputs'],16)
        self.assertTrue(all(row['expected']['gate']==2 for row in result['cases']))
    def test_wrong_answers_remain_wrong_without_calculator_repair(self):
        result=self.check(fixture('wrong-answers'));self.assertEqual(result['metrics']['rawAnswerCorrectForDeliveredDocument'],0)
        self.assertEqual(result['metrics']['failedRequiredOutputs'],16)
    def test_first_tie_and_zero_shortage_reference(self):
        self.assertEqual(oracle.answer({'rows':[{'sku':'first','available':2,'forecast':5},{'sku':'tied','available':0,'forecast':3}]}),{'sku':'first','units':3})
        self.assertEqual(oracle.answer({'rows':[{'sku':'first','available':4,'forecast':1},{'sku':'next','available':0,'forecast':0}]}),{'sku':'first','units':0})
        for content in ['{"sku":"A0","units":true}','{"sku":"A0","sku":"A1","units":1}']:
            self.assertIsNone(trial.parsed_answer(content));self.assertIsNone(oracle.parsed(content))
    def test_tampered_raw_response_or_zero_tokens_rejected(self):
        data=fixture();data['calls'][1]['responseUtf8']+=' '
        with self.assertRaisesRegex(ValueError,'digest'):self.check(data)
        data=fixture();data['calls'][1]['tokensGenerated']=True
        with self.assertRaisesRegex(ValueError,'Generated-token'):self.check(data)
    def test_tampered_context_or_host_effect_rejected(self):
        data=fixture();data['calls'][1]['wireRequest']['prompt']+='BUY'
        with self.assertRaisesRegex(ValueError,'Wire request'):self.check(data)
        data=fixture();data['cases'][0]['hostEvents'][0]['hostEffect']='new_virtual_payment'
        with self.assertRaisesRegex(ValueError,'Harness host state'):self.check(data)
    def test_missing_case_or_pre_registration_call_rejected(self):
        data=fixture();data['cases'].pop()
        with self.assertRaisesRegex(ValueError,'eight'):self.check(data)
        data=fixture();data['calls'][1]['startedAtUtc']='2026-11-01T00:00:00+00:00'
        with self.assertRaisesRegex(ValueError,'predates registration'):self.check(data)

if __name__=='__main__':unittest.main(verbosity=2)
