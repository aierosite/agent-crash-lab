"""Declared constructed receipt envelopes around original actual SDK args/logs."""
from pathlib import Path
from hashlib import sha256
import base64,json,runpy
H=Path(__file__).resolve().parent
pack=lambda v:json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def bundle(episode):
 observations=[];bindings=[]
 for i,row in enumerate(episode['sdkRows']):
  key=episode['id']+'/'+str(i);tx,rid,block=[sha256((key+s).encode()).hexdigest()[:44] for s in ['tx','receipt','block']]
  action={'FunctionCall':{'method_name':'ft_transfer','args':base64.b64encode(pack(row['args'])).decode(),'deposit':'1','gas':30000000000000}}
  def outcome(oid,executor,children,status,logs):return {'id':oid,'block_hash':block,'outcome':{'executor_id':executor,'receipt_ids':children,'status':status,'logs':logs,'gas_burnt':1,'tokens_burnt':'0'}}
  status={'SuccessValue':''};result={'final_execution_status':'FINAL','status':status,'transaction':{'hash':tx,'signer_id':'payer.testnet','receiver_id':'token.testnet','actions':[action]},'transaction_outcome':outcome(tx,'payer.testnet',[rid],{'SuccessReceiptId':rid},[]),'receipts_outcome':[outcome(rid,'token.testnet',[],status,row['logs'])],'receipts':[{'receipt_id':rid,'predecessor_id':'payer.testnet','receiver_id':'token.testnet','receipt':{'Action':{'signer_id':'payer.testnet','actions':[action],'input_data_ids':[],'output_data_receivers':[]}}}]}
  observations.append({'id':'billing-sdk-'+str(i),'request':{'jsonrpc':'2.0','id':str(i),'method':'tx_status','params':{'tx_hash':tx,'sender_account_id':'payer.testnet','wait_until':'FINAL'}},'response':{'jsonrpc':'2.0','id':str(i),'result':result}});bindings.append({'id':'billing-payment-'+str(i),'intent':'bill','tx_hash':tx,'receipt_id':rid})
 evidence={'format':'agent-crash-lab/token-execution-v1','network':'sandbox','source':{'kind':'synthetic','note':'Actual local-model selected localhost tools executed actual canonical SDK mock ft_transfer args/event strings. Receipt/transaction/block IDs, gas, FINAL and JSON-RPC envelopes here are constructed. No actual bank, deployed WASM, chain RPC, signing or consensus observation.'},'observations':observations}
 task={'format':'agent-crash-lab/token-task-v1','profile':'near-nep141-sdk-receipts/v1','authority':{'kind':'reconstructed','note':'Registered source-informed fictional invoice policy, not signed customer authority.'},'evidence_sha256':sha256(pack(evidence)).hexdigest(),'network':'sandbox','token_contract':'token.testnet','payer':'payer.testnet','closed_horizon':episode['executionComplete'],'horizon_note':'Only this bounded recorded trajectory is supplied; aborted/truncated model execution retains an open horizon.','intents':[{'id':'bill','recipient':'bill.testnet','max_gross':'9870','min_settled':'9870','max_burn':'0'}],'bindings':bindings}
 return task,evidence
def assess(episode):
 task,evidence=bundle(episode);report=runpy.run_path(str(H/'inspector/token_policy.py'))['assess'](pack(task),pack(evidence));return {'invoked':True,'gate':report['gate'],'report':report}
