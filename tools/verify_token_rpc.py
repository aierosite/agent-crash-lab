"""Offline corroboration of two published fixtures against separately collected public-node bytes."""
from pathlib import Path
from hashlib import sha256
import base64,json,struct,re
class EvidenceError(ValueError):pass
def need(ok,why):
 if not ok:raise EvidenceError(why)
def unique(pairs):
 d={}
 for k,v in pairs:need(k not in d,'Duplicate JSON field');d[k]=v
 return d
def read_json(path,allow_float=False):
 raw=path.read_bytes();need(len(raw)<=2097152,'Evidence file exceeds 2 MiB')
 def reject_float(_):raise EvidenceError('RPC protocol numbers must use integer JSON representation')
 return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_float=float if allow_float else reject_float,parse_constant=lambda _:(_ for _ in ()).throw(EvidenceError('Non-finite JSON number')))
def unb64(s):
 need(type(s) is str and len(s)<=2097152,'Invalid base64 value')
 try:b=base64.b64decode(s,validate=True)
 except (ValueError,TypeError) as e:raise EvidenceError('Invalid base64 encoding') from e
 need(base64.b64encode(b).decode()==s,'Noncanonical base64 encoding');return b
class Reader:
 def __init__(self,b):self.b=b;self.i=0
 def take(self,n):
  need(type(n) is int and 0<=n<=65536 and self.i+n<=len(self.b),'Truncated or oversized Borsh field');out=self.b[self.i:self.i+n];self.i+=n;return out
 def uint(self,n):return int.from_bytes(self.take(n),'little')
 def vector(self):return self.take(self.uint(4))
 def account(self):
  try:s=self.vector().decode('ascii')
  except UnicodeError as e:raise EvidenceError('Non-ASCII account ID') from e
  need(2<=len(s)<=64 and re.fullmatch('[a-z0-9]+(?:[._-][a-z0-9]+)*',s) is not None,'Invalid account ID');return s
 def end(self):need(self.i==len(self.b),'Unexpected trailing Borsh bytes')
def account_key(prefix,account):
 b=account.encode('ascii');return prefix+struct.pack('<I',len(b))+b
def state_map(result):
 need(type(result) is dict and 'error' not in result and type(result.get('values')) is list and not result.get('last_key'),'Incomplete or failed state query')
 out={}
 for i,row in enumerate(result['values']):
  need(type(row) is dict and set(row)=={'key','value'},'Unexpected state entry');k,v=unb64(row['key']),unb64(row['value']);need(k not in out,'Duplicate storage key');out[k]=(i,v)
 need(b'STATE' in out,'Contract state root is missing');return out
def token_balance(result,vault):
 values=state_map(result);root=Reader(values[b'STATE'][1]);need(root.vector()==b't','Unsupported token storage prefix');supply=root.uint(16);usage=root.uint(8);root.end()
 total=0;owners={}
 for key,(i,value) in values.items():
  if key==b'STATE':continue
  need(key[:1]==b't','Unexpected token storage key');r=Reader(key[1:]);owner=r.account();r.end();need(owner not in owners and len(value)==16,'Invalid token balance record');owners[owner]=(i,int.from_bytes(value,'little'));total+=owners[owner][1]
 need(total==supply,'Stored token balances do not sum to total supply');need(vault in owners,'Selected vault has no stored balance record')
 i,balance=owners[vault];return {'held':str(balance),'totalSupply':str(supply),'accountStorageUsage':usage,'balances':{owner:str(row[1]) for owner,row in owners.items()},'proof':{'pointer':f'/result/values/{i}/value','key':base64.b64encode(account_key(b't',vault)).decode(),'byteOffset':0,'byteLength':16}}
def treasury(result,accounts):
 values=state_map(result);need(set(values)=={b'STATE'},'Unexpected treasury storage key');i,raw=values[b'STATE'];r=Reader(raw);ids=[r.account() for _ in range(3)];need(ids==[accounts['user'],accounts['agent'],accounts['token']],'Treasury owner/agent/token identities disagree')
 fields={};proofs={}
 for key in ['credit','reserved','pending','allowance']:
  offset=r.i;fields[key]=str(r.uint(16));proofs[key]={'pointer':f'/result/values/{i}/value','byteOffset':offset,'byteLength':16}
 r.end();fields['liabilities']=str(sum(int(fields[k]) for k in ['credit','reserved','pending']));return {'fields':fields,'proofs':proofs,'owner':ids[0]}
def historical_ref(result,accounts):
 values=state_map(result);root=Reader(values[b'STATE'][1]);owner=root.account();fees=[root.uint(4),root.uint(4)];pools=root.uint(8);pool_prefix=root.vector();deposit_prefix=root.vector();index_prefix=root.vector();whitelist_length=root.uint(8);element_prefix=root.vector();root.end()
 need(owner==accounts['user'] and pools==0 and pool_prefix==b'p' and deposit_prefix==b'd' and index_prefix==b'wi' and element_prefix==b'we','Unsupported historical Ref root layout or pool/owner scope')
 deposits={};proofs={}
 for key,(i,value) in values.items():
  if not key.startswith(deposit_prefix):continue
  r=Reader(key[len(deposit_prefix):]);who=r.account();r.end();r=Reader(value);r.uint(16);count=r.uint(4);need(count<=1024,'Too many deposited token types');tokens={};last=''
  for _ in range(count):
   token=r.account();need(token>last and token not in tokens,'Duplicate or unordered deposit token');last=token;offset=r.i;tokens[token]=r.uint(16)
   if token==accounts['token']:proofs[who]={'pointer':f'/result/values/{i}/value','key':base64.b64encode(key).decode(),'byteOffset':offset,'byteLength':16}
  r.end();deposits[who]=tokens
 need(set(deposits)=={accounts['user']} and accounts['token'] in deposits[accounts['user']],'Unsupported multi-owner or missing deposit scope')
 credit=deposits[accounts['user']][accounts['token']]
 return {'fields':{'credit':str(credit),'pending':'0','reserved':'0','liabilities':str(credit)},'proofs':{'credit':proofs[accounts['user']]},'owner':owner,'pools':pools,'whitelistLength':whitelist_length,'fees':fees}
def result(folder):
 req=read_json(folder/'request.json');res=read_json(folder/'response.json');observation=read_json(folder/'observation.json',allow_float=True)
 need(observation['endpoint']=='https://archival-rpc.testnet.near.org' and observation.get('httpStatus')==200 and observation.get('signed') is False,'Capture endpoint, status or request mode is unsupported')
 need(sha256((folder/'request.json').read_bytes()).hexdigest()==observation['requestSha256'] and sha256((folder/'response.json').read_bytes()).hexdigest()==observation['responseSha256'],'Capture byte hashes disagree')
 need(req.get('jsonrpc')=='2.0' and res.get('jsonrpc')=='2.0' and req.get('id')==res.get('id') and 'error' not in res and type(res.get('result')) is dict and 'error' not in res['result'],'Missing, errored or mismatched RPC response')
 need(req['method'] in ['status','block','tx','tx_status','query'],'Unexpected non-read-only method')
 if req['method']=='query':need(req['params']['request_type'] in ['view_account','view_state'],'Contract execution is outside this capture scope')
 return req,res['result'],observation
def outcome_projection(d):
 def row(o):return {'id':o['id'],'block_hash':o['block_hash'],'outcome':{k:o['outcome'][k] for k in ['executor_id','status','receipt_ids','logs','gas_burnt','tokens_burnt']}}
 need(type(d['receipts_outcome']) is list,'Missing receipt outcomes');ids=[o['id'] for o in d['receipts_outcome']];need(len(ids)==len(set(ids)) and d['transaction_outcome']['id'] not in ids,'Duplicate transaction or receipt outcome identity')
 return {'final_execution_status':d['final_execution_status'],'status':d['status'],'transaction':d['transaction'],'transaction_outcome':row(d['transaction_outcome']),'receipts_outcome':{o['id']:row(o) for o in d['receipts_outcome']}}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def code_hash(digest):
 need(type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest) is not None,'Invalid artifact SHA-256');b=bytes.fromhex(digest);n=int.from_bytes(b,'big');s='';alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
 while n:n,m=divmod(n,58);s=alphabet[m]+s
 return '1'*(len(b)-len(b.lstrip(b'\0')))+s
def operation_reference(tx,accounts,points,kind):
 before,after=[p['fields'] for p in points];rights=lambda p:sum(int(p[k]) for k in ['credit','pending','reserved'])
 t=tx['transaction'];need(t['receiver_id']==accounts['target'] and len(t['actions'])==1 and 'FunctionCall' in t['actions'][0],'Unsupported root action for the selected operation reference');call=t['actions'][0]['FunctionCall']
 args=json.loads(unb64(call['args']),object_pairs_hook=unique);method='withdraw' if kind=='failed' else 'execute';actor=accounts['user'] if kind=='failed' else accounts['agent']
 need(call['method_name']==method and t['signer_id']==actor,'The source operation/actor does not match the declared reference')
 expected_args={'token_id':accounts['token'],'amount':'4000000','unregister':False} if kind=='failed' else {'receiver_id':accounts['user']};need(args==expected_args,'The selected operation arguments changed')
 amount=4000000 if kind=='failed' else int(before['reserved']);expected_rights=rights(before) if kind=='failed' else rights(before)-amount
 reference={'id':'failed-owner-withdrawal-preserves-rights' if kind=='failed' else 'reserved-payment-delivers-and-debits-once','reference':'An unsuccessful token payout must preserve these user rights.' if kind=='failed' else 'Deliver the prior reservation to the recorded owner and debit that amount once.',
  'status':'inconclusive','rootSucceeded':'SuccessValue' in tx['status'],'expectedRightsAfter':str(expected_rights),'observedRightsAfter':str(rights(after)),'expectedTokenDelivery':'0' if kind=='failed' else str(amount),'observedTokenDelivery':None,'payout':None,'reason':None}
 receipts=tx.get('receipts',[]);need(type(receipts) is list,'Invalid receipt-body list');ids=[r['receipt_id'] for r in receipts];need(len(ids)==len(set(ids)),'Duplicate receipt body identity')
 outcomes={r['id']:(i,r) for i,r in enumerate(tx['receipts_outcome'])};payouts=[]
 for i,r in enumerate(receipts):
  if 'Action' in r.get('receipt',{}):need(r['receipt_id'] in outcomes and r['receiver_id']==outcomes[r['receipt_id']][1]['outcome']['executor_id'],'Action body is not bound to its receipt outcome receiver')
  if r.get('receiver_id')!=accounts['token'] or r.get('predecessor_id')!=accounts['target']:continue
  body=r.get('receipt',{}).get('Action',{});actions=body.get('actions',[])
  if len(actions)!=1 or 'FunctionCall' not in actions[0]:continue
  fc=actions[0]['FunctionCall']
  if fc.get('method_name')!='ft_transfer':continue
  need(body.get('signer_id')==t['signer_id'],'Payout signer propagation differs from the root transaction')
  a=json.loads(unb64(fc['args']),object_pairs_hook=unique)
  need(a.get('receiver_id')==accounts['user'] and a.get('amount')==str(amount) and fc.get('deposit')=='1','Payout receipt does not match the reference amount/recipient')
  need(r['receipt_id'] in outcomes,'Payout body has no captured outcome');oi,o=outcomes[r['receipt_id']];need(o['outcome']['executor_id']==accounts['token'],'Payout outcome executor mismatch');tag=next(iter(o['outcome']['status']))
  payouts.append({'receiptId':r['receipt_id'],'method':'ft_transfer','amount':str(amount),'recipient':a['receiver_id'],'outcome':tag,'actionPointer':f'/result/receipts/{i}/receipt/Action/actions/0/FunctionCall','statusPointer':f'/result/receipts_outcome/{oi}/outcome/status'})
 if not payouts:reference['reason']='Relevant payout receipt body is absent; method/recipient binding remains inconclusive.';return reference
 need(len(payouts)==1,'Ambiguous payout receipt bodies');payout=payouts[0];delivered=0
 for o in tx['receipts_outcome']:
  outcome=o['outcome']
  if outcome['executor_id']!=accounts['token'] or not any(k in outcome['status'] for k in ['SuccessValue','SuccessReceiptId']):continue
  for line in outcome['logs']:
   if not line.startswith('EVENT_JSON:'):continue
   event=json.loads(line[11:],object_pairs_hook=unique)
   if event.get('standard')!='nep141' or event.get('event')!='ft_transfer':continue
   need(event.get('version')=='1.0.0','Unsupported transfer event version')
   for item in event['data']:
    if item.get('old_owner_id')==accounts['target'] and item.get('new_owner_id')==accounts['user']:
     n=item.get('amount');need(type(n) is str and re.fullmatch('0|[1-9][0-9]{0,38}',n) is not None and int(n)<2**128,'Invalid delivered amount');delivered+=int(n)
 condition=payout['outcome']=='Failure' and delivered==0 if kind=='failed' else payout['outcome'] in ['SuccessValue','SuccessReceiptId'] and delivered==amount
 reference.update(payout=payout,observedTokenDelivery=str(delivered))
 if not condition:reference['reason']='Payout execution no longer matches the selected reference precondition.';return reference
 reference['status']='passed' if rights(after)==expected_rights else 'failed';return reference
def verify(captures,recordings):
 expected=read_json(captures/'EXPECTED-FROM-PUBLISHED.json');need(set(expected['cases'])=={'upstream-failed-withdrawal','ai-payment'},'This verifier supports only the two documented artifact/schema cases');loaded=set()
 def observe(folder):loaded.add(folder.relative_to(captures).as_posix());return result(folder)
 status_request,status,_=observe(captures/'01-status');need(status_request['method']=='status' and status_request['params']==[] and status['chain_id']=='testnet','The node did not identify testnet')
 paths=[p for p in captures.iterdir() if p.is_dir() and (p/'request.json').exists()];folders={p.name.split('-',1)[1]:p for p in paths};need(len(paths)==len(folders)==23,'Unexpected capture inventory');output=[]
 for cid,definition in expected['cases'].items():
  label='failed' if cid.startswith('upstream') else 'allowed';accounts=definition['accounts'];recording=read_json(recordings/(cid+'.json'));step=recording['steps'][-1];points=[]
  need(recording['source']['sha256']==definition['sourceSha256'],'Published archive binding changed')
  for side in ['before','after']:
   snapshot=definition[side];block=snapshot['blockHash'];height=snapshot['blockHeight'];block_folder=captures/'02-original-block' if label=='failed' and side=='before' else folders[label+'-'+side+'-block'];req,header_result,_=observe(block_folder)
   need(req['method']=='block' and req['params']=={'block_id':block} and header_result['header']['hash']==block and header_result['header']['height']==height,'Header differs from the requested published block')
   observations={};identities={}
   for role in ['token','target']:
    for kind in ['account','state']:
     folder=folders[label+'-'+side+'-'+role+'-'+kind];req,r,meta=observe(folder);params={'request_type':'view_'+kind,'block_id':block,'account_id':accounts[role]}
     if kind=='state':params['prefix_base64']=''
     need(req['method']=='query' and req['params']==params and r.get('block_hash')==block and r.get('block_height')==height,'State/account query lost its account or block binding')
     observations[(role,kind)]=(r,folder.name,meta['responseSha256'])
    artifact=next(a for a in definition['artifactClaims'] if a['accountId']==accounts[role]);reported=observations[(role,'account')][0]['code_hash']
    supported='d797affb5549a8be5a6019510b9ecab7d05a4291f146499e305e320643b25ced' if role=='token' else 'f0ec34d5365e38d62a4751bd0c3c95423a1077a930fb882ad54f79ad322e3b84' if label=='failed' else '0ef6d6609effb1dc9ac1a8d966c334a1802eca58751b94fe589ec8a81876271f'
    need(artifact['sha256']==supported and reported==artifact['codeHash']==code_hash(supported),'Node-reported deployed code differs from this supported artifact/schema identity');identities[role]=reported
   token=token_balance(observations[('token','state')][0],accounts['target']);ledger=historical_ref(observations[('target','state')][0],accounts) if label=='failed' else treasury(observations[('target','state')][0],accounts)
   actual={'held':token['held'],**{k:ledger['fields'][k] for k in ['credit','pending','reserved','liabilities']}}
   original={'held':snapshot['targetTokens'],**{k:snapshot.get(k,'0') for k in ['credit','pending','reserved','liabilities']}}
   need(actual==original,'Raw stored values differ from published endpoint summaries')
   need(all(step[side][k]==actual[k] for k in actual),'Normalized public recording differs from raw corroborated values')
   if 'allowance' in ledger['fields']:need(ledger['fields']['allowance']==snapshot['allowance'],'Allowance differs from stored ledger')
   if label=='allowed':need(token['balances'].get(accounts['user'])==snapshot['userTokens'],'Recorded recipient balance differs from raw stored token balance')
   points.append({'side':side,'blockHash':block,'blockHeight':height,'fields':actual,'codeIdentities':identities,'tokenProof':token['proof'],'rightsProofs':ledger['proofs'],'headerCapture':block_folder.relative_to(captures).as_posix(),'rawQueries':[{'kind':role+'-'+kind,'folder':folder,'responseSha256':digest} for (role,kind),(_,folder,digest) in observations.items()]})
  req,tx,_=observe(folders[label+'-tx']);need(req['method']=='tx' and req['params']=={'tx_hash':definition['transactionId'],'sender_account_id':step['transactions'][0]['result']['transaction']['signer_id'],'wait_until':'FINAL'},'Unexpected transaction status request')
  need(tx['final_execution_status']=='FINAL' and canonical(outcome_projection(tx))==canonical(outcome_projection(step['transactions'][0]['result'])),'Fresh transaction outcomes disagree with the published factual extraction')
  detail_folder=captures/'receipt-details'/('24-failed-tx-status' if label=='failed' else '25-allowed-tx-status');detail_request,detail,_=observe(detail_folder)
  need(detail_request['method']=='tx_status' and detail_request['params']==req['params'] and canonical(outcome_projection(detail))==canonical(outcome_projection(tx)),'Receipt-details request or execution outcomes disagree with the original status query')
  reference=operation_reference(detail,accounts,points,label)
  output.append({'case':cid,'recordingSha256':sha256((recordings/(cid+'.json')).read_bytes()).hexdigest(),'points':points,'transactionId':definition['transactionId'],'transactionOutcomeProjectionMatches':True,'transactionCapture':folders[label+'-tx'].relative_to(captures).as_posix(),'receiptDetailsCapture':detail_folder.relative_to(captures).as_posix(),'operationReference':reference})
 need(len(loaded)==25,'Some captured reads were not used');inventory={}
 for name in sorted(loaded):
  for file in ['request.json','response.json','observation.json']:
   path=captures/name/file;raw=path.read_bytes();inventory[name+'/'+file]={'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
 raw=(captures/'EXPECTED-FROM-PUBLISHED.json').read_bytes();inventory['EXPECTED-FROM-PUBLISHED.json']={'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
 times=[read_json(captures/name/'observation.json',allow_float=True) for name in loaded]
 return {'format':'agent-crash-lab/rpc-corroboration-v2','cases':output,'provider':'https://archival-rpc.testnet.near.org','network':'testnet','capturedReadRequests':len(loaded),'capturedAtStart':min(x['startedAtUtc'] for x in times),'capturedAtEnd':max(x['finishedAtUtc'] for x in times),'replayNetworkCalls':0,'transactionSubmissions':0,'contractExecutions':0,'signatureOrStateProofVerified':False,'independentGrading':False,'datasetSha256':sha256(canonical(inventory)).hexdigest(),'verifierSha256':sha256(Path(__file__).read_bytes()).hexdigest(),'meaning':'Separately collected public-node observations agree with selected published fields. Operation references are explicit and source-informed, not independently authored grading. Trusts the endpoint and supported storage/artifact schemas; no consensus/state-proof authentication or interval-exclusivity proof.'}
if __name__=='__main__':
 import argparse
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--captures',type=Path,default=root/'verification/rpc-study');p.add_argument('--recordings',type=Path,default=root/'verification/token-study');p.add_argument('--output',type=Path);a=p.parse_args()
 try:
  r=verify(a.captures,a.recordings)
  if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n','utf-8')
  print(json.dumps(r));raise SystemExit(0)
 except (OSError,ValueError,KeyError,TypeError) as e:print(json.dumps({'error':str(e)[:300]}));raise SystemExit(2)
