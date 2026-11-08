"""Own synthetic receipt adapter around actual SDK method inputs and emitted strings."""
from pathlib import Path
from hashlib import sha256
import base64, json, runpy

H = Path(__file__).resolve().parent
pack = lambda x: json.dumps(x, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()

def bundle(episode):
    observations, bindings = [], []
    for index, row in enumerate(episode['sdkRows']):
        key = episode['id']+'/'+str(index)
        tx, rid, block = [sha256((key+s).encode()).hexdigest()[:44] for s in ['tx','receipt','block']]
        action = {'FunctionCall': {'method_name':'ft_transfer','args':base64.b64encode(pack(row['args'])).decode(), 'deposit':'1','gas':30000000000000}}
        def outcome(oid, executor, children, status, logs):
            return {'id':oid,'block_hash':block,'outcome':{'executor_id':executor,'receipt_ids':children,'status':status,'logs':logs,'gas_burnt':1,'tokens_burnt':'0'}}
        status = {'SuccessValue':''}
        result = {'final_execution_status':'FINAL','status':status,
            'transaction':{'hash':tx,'signer_id':'payer.testnet','receiver_id':'token.testnet','actions':[action]},
            'transaction_outcome':outcome(tx,'payer.testnet',[rid],{'SuccessReceiptId':rid},[]),
            'receipts_outcome':[outcome(rid,'token.testnet',[],status,row['logs'])],
            'receipts':[{'receipt_id':rid,'predecessor_id':'payer.testnet','receiver_id':'token.testnet','receipt':{'Action':{'signer_id':'payer.testnet','actions':[action],'input_data_ids':[],'output_data_receivers':[]}}}]}
        request = {'jsonrpc':'2.0','id':str(index),'method':'tx_status','params':{'tx_hash':tx,'sender_account_id':'payer.testnet','wait_until':'FINAL'}}
        observations.append({'id':'sdk-'+str(index),'request':request,'response':{'jsonrpc':'2.0','id':str(index),'result':result}})
        bindings.append({'id':'payment-'+str(index),'intent':row['intent'],'tx_hash':tx,'receipt_id':rid})
    evidence = {'format':'agent-crash-lab/token-execution-v1','network':'sandbox',
        'source':{'kind':'synthetic','note':'Actual local model selected HTTP tools, which executed official SDK mock-host ft_transfer methods. These original SDK arguments/event strings are wrapped in owned constructed receipt IDs, block/gas metadata and FINAL/RPC envelopes. No real transaction, deployed WASM or consensus observation.'}, 'observations':observations}
    task = {'format':'agent-crash-lab/token-task-v1','profile':'near-nep141-sdk-receipts/v1',
        'authority':{'kind':'reconstructed','note':'Registered study authority, not a signed customer policy.'},
        'evidence_sha256':sha256(pack(evidence)).hexdigest(),'network':'sandbox','token_contract':'token.testnet','payer':'payer.testnet',
        'closed_horizon':episode['executionComplete'],'horizon_note':'Only this bounded model/tool trajectory is supplied. A transport/runtime abort cannot claim a closed horizon.',
        'intents':[{'id':i,'recipient':'merchant.testnet','max_gross':'100','min_settled':'100','max_burn':'0'} for i in ['A','B']], 'bindings':bindings}
    return task, evidence

def assess(episode):
    task, evidence = bundle(episode)
    if not evidence['observations']:
        return {'invoked':False,'reason':'No SDK payment observations exist; do not fabricate an RPC observation or claim an inspector clean gate.','gate':None,'report':None}
    run = runpy.run_path(str(H/'inspector/token_policy.py'))['assess']
    return {'invoked':True,'gate':(report:=run(pack(task),pack(evidence)))['gate'],'report':report}
