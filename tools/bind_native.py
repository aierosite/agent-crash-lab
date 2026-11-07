"""Bind the fresh native captures to independent predeclared caps and references."""
from pathlib import Path
from datetime import datetime,timezone
from runpy import run_path
import base64,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
assess=run_path(str(ROOT/'agent_crash_lab.py'))['assess']
def main():
    raw=(ROOT/'evidence/native-observation.json').read_bytes();pre=(ROOT/'evidence/native-precommit.json').read_bytes()
    data=json.loads(raw);basis=json.loads(pre);assert data['ownedNodeStopped']
    summary={'atUtc':data['atUtc'],'classification':'Actual fresh owned local NEAR sandbox execution with scripted workers, process crash77 and restart; known-family source-informed integration, not live-model performance','successful':True,'ownedNodeStopped':data['ownedNodeStopped'],'nativeSendAttempts':data['nativeSendAttempts'],'evidenceSha256':hashlib.sha256(raw).hexdigest(),'precommitSha256':hashlib.sha256(pre).hexdigest(),'runnerSha256':hashlib.sha256((ROOT/'tools/native_crash.py').read_bytes()).hexdigest(),'policies':[]}
    baselines=json.loads((ROOT/'BASELINES.json').read_text())
    expected=json.loads((ROOT/'EXPECTED.json').read_text())
    for index,run in enumerate(data['runs']):
        policy=run['policy'];name='native-'+policy
        task={'format':'agent-crash-lab/task-v1','profile':'near-sandbox-2.14/native-v1','authority':{'kind':'historical_controlled','basis':[{'source':'basis','pointer':''}],'note':'Independent expected caps/documents written before these actual local trials. Owner/hash binding follows observed send indices; same operator, scripted workers, not an external holdout.'},'sources':{'recording':summary['evidenceSha256'],'basis':summary['precommitSha256']},'run':{'id':name,'chain_id':run['chainId'],'protocol_version':run['protocolVersion'],'capture':{'source':'recording','pointer':'/runs/'+str(index)},'closed_horizon':True,'horizon_note':'All controlled sends from crashed/resumed A and independent B are captured, all hashes expanded by independent local observer, owned node stopped; no future process guarantee.'},'intents':[{'id':i,'protected_accounts':[data['owner']],'merchant':data['merchant']} for i in ['A','B']],'attempts':[],'constraints':[],'utility':{'required':[],'intermediate':[]}}
        for si,send in enumerate(run['sends']):
            record=run['rpcObservations'][send['index']]
            task['attempts'].append({'id':'send-'+str(si),'tx_hash':send['hash'],'role':'task','intent':send['intent'],'submissions':[{'ref':{'source':'recording','pointer':f'/runs/{index}/rpcObservations/{send["index"]}'},'packet_sha256':hashlib.sha256(base64.b64decode(record['request']['params']['signed_tx_base64'])).hexdigest()}]})
        for tid in ['A','B']:
            task['constraints'].extend([{'id':tid+'-merchant','intent':tid,'metric':'merchant_gross_principal','cap':basis['cap']},{'id':tid+'-count','intent':tid,'metric':'committed_settlement_attempts','cap':'1'}])
        for ui,tid in enumerate(['A','B']):task['utility']['required'].append({'id':tid+'-answer','intent':tid,'profile':'inventory-gap-first-v1','observation':{'source':'recording','pointer':f'/runs/{index}/utilityObservations/{ui}'},'expected_document':basis['expectedDocuments'][tid],'expected_answer':basis['expectedAnswer']})
        taskbytes=(json.dumps(task,indent=2)+'\n').encode();(ROOT/('tasks/'+name+'.json')).write_bytes(taskbytes)
        report=assess(taskbytes,{'recording':raw,'basis':pre})
        (ROOT/('verification/'+name+'-report.json')).write_text(json.dumps(report,indent=2))
        assert report['invocation']['status']=='assessed',report['invocation']
        amounts={c['intent']:c for c in report['constraints'] if c['metric']=='merchant_gross_principal'}
        assert all(amounts[i]['exact_total']==basis['expectedPolicies'][policy][i] for i in ['A','B'])
        assert amounts['A']['status']==('breached' if policy=='naive' else 'within') and amounts['B']['status']=='within'
        assert all(u['status']=='passed' for u in report['utility']['required'])
        summary['policies'].append({'id':policy,'name':'Naive retry' if policy=='naive' else 'Durable hash journal','intentAGross':amounts['A']['exact_total'],'intentBGross':amounts['B']['exact_total'],'answer':run['utilityObservations'][0]['scriptedAnswer'],'crashExitCode':run['workers'][0]['exitCode'],'recovery':'new transaction sent' if policy=='naive' else 'known transaction re-fetched; no new A send','merchantBalanceIncrease':run['merchantBalanceIncrease'],'financialStatus':amounts['A']['status'],'requiredOutputsPassed':2,'baseline':name})
        baselines=[b for b in baselines if b['name']!=name]+[{'name':name,'task':'tasks/'+name+'.json','sources':{'recording':'evidence/native-observation.json','basis':'evidence/native-precommit.json'}}]
        expected[name]={'intents':{i:{'merchant_gross':basis['expectedPolicies'][policy][i],'cap':basis['cap'],'merchant_status':'breached' if policy=='naive' and i=='A' else 'within'} for i in ['A','B']},'required_utility_statuses':['passed','passed']}
    (ROOT/'BASELINES.json').write_text(json.dumps(baselines,indent=2)+'\n')
    (ROOT/'EXPECTED.json').write_text(json.dumps(expected,indent=2)+'\n')
    (ROOT/'verification/native-crash-comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
if __name__=='__main__':main()
