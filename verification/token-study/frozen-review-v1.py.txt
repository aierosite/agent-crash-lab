"""Conditional consistency review of recorded NEP-141 custody transitions, not an authorization gate."""
from pathlib import Path
from hashlib import sha256
import argparse,json,re,sys

FORMAT='agent-crash-lab/token-recording-v1'
REPORT='agent-crash-lab/token-review-v1'
MAX_BYTES=2*1024*1024
U128=2**128
ASSUMPTIONS=[
 'Endpoint balances and rights are producer-reported summaries, not authenticated state proofs.',
 'All vault rights belong to one owner and no unrelated change occurs within a recorded interval.',
 'The declared token implementation emits truthful events and the archived FINAL outcomes are authentic.',
]
class ReviewError(ValueError):pass
def pack(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def require(ok,message):
 if not ok:raise ReviewError(message)
def unique(pairs):
 out={}
 for key,value in pairs:
  require(key not in out,'The recording repeats a JSON field. Each field must appear once.');out[key]=value
 return out
def decode(raw):
 require(type(raw) is bytes and 0<len(raw)<=MAX_BYTES,'Choose a nonempty JSON recording no larger than 2 MiB.')
 try:
  value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ReviewError('JSON numbers must be finite.')))
  stack=[(value,0)];nodes=0
  while stack:
   v,depth=stack.pop();nodes+=1
   require(depth<=64 and nodes<=120000,'This recording is too deeply nested or contains too many fields.')
   if type(v) is dict:stack.extend((x,depth+1) for pair in v.items() for x in pair)
   elif type(v) is list:stack.extend((x,depth+1) for x in v)
   elif type(v) is str:require(not any(0xd800<=ord(c)<=0xdfff for c in v),'The recording contains invalid Unicode text.')
   elif type(v) is float:raise ReviewError('Use exact whole numbers; decimal token amounts must be strings of atomic units.')
  return value
 except (UnicodeError,json.JSONDecodeError,RecursionError) as e:raise ReviewError('The recording is not valid, bounded UTF-8 JSON.') from e
def obj(value,keys,where):
 require(type(value) is dict and set(value)==set(keys),f'{where} has missing or unexpected fields.')
 return value
def text(value,where,limit=256):
 require(type(value) is str and 0<len(value)<=limit,f'{where} must be nonempty text within {limit} characters.')
 return value
def amount(value,where):
 require(type(value) is str and re.fullmatch(r'0|[1-9][0-9]{0,38}',value) is not None and int(value)<U128,f'{where} must be an unsigned 128-bit integer string, with no leading zeros.')
 return int(value)
def account(value):
 require(type(value) is str and 2<=len(value)<=64 and re.fullmatch(r'[a-z0-9]+(?:[._-][a-z0-9]+)*',value) is not None,'An account ID is invalid.')
 return value
def hexhash(value):
 require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None,'A source or artifact SHA-256 is invalid.')
 return value
def b58(raw):
 alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';n=int.from_bytes(raw,'big');s=''
 while n:n,r=divmod(n,58);s=alphabet[r]+s
 return '1'*(len(raw)-len(raw.lstrip(b'\0')))+s
def snapshot(s):
 obj(s,['block_hash','block_height','held','credit','pending','reserved','liabilities'],'Snapshot')
 text(s['block_hash'],'Block hash',64)
 require(type(s['block_height']) is int and 0<s['block_height']<=2**53-1,'Snapshot height must be a positive exact integer.')
 return {k:amount(s[k],k) for k in ['held','credit','pending','reserved','liabilities']}
def outcomes(result):
 require(type(result) is dict,'A transaction result must be an object.')
 require(type(result.get('transaction')) is dict and type(result.get('transaction_outcome')) is dict and type(result.get('receipts_outcome')) is list,'A transaction needs its root and receipt outcomes.')
 require(len(result['receipts_outcome'])<=4096,'A transaction contains too many receipts.')
 txid=text(result['transaction'].get('hash'),'Transaction hash',64)
 all_nodes=[result['transaction_outcome'],*result['receipts_outcome']];by_id={};complete=result.get('final_execution_status')=='FINAL'
 final=result.get('status')
 if type(final) is not dict or len(final)!=1 or next(iter(final)) not in ['SuccessValue','Failure']:complete=False
 require(result['transaction_outcome'].get('id')==txid,'The transaction outcome does not match its transaction hash.')
 for row in all_nodes:
  require(type(row) is dict,'A receipt outcome must be an object.')
  rid=text(row.get('id'),'Receipt ID',64);require(rid not in by_id,'A receipt ID occurs more than once. Remove conflicting or duplicated outcomes.')
  o=row.get('outcome');require(type(o) is dict,'A receipt is missing its outcome.')
  account(o.get('executor_id'));text(row.get('block_hash'),'Outcome block hash',64)
  children=o.get('receipt_ids');logs=o.get('logs');status=o.get('status')
  require(type(children) is list and len(children)<=4096 and len(set(text(c,'Child receipt ID',64) for c in children))==len(children),'Receipt child IDs must be unique.')
  require(type(logs) is list and len(logs)<=1024 and all(type(x) is str and len(x)<=65536 for x in logs),'Receipt logs exceed their allowed size or shape.')
  require(type(status) is dict and len(status)==1,'Each receipt needs one execution status.')
  tag=next(iter(status));require(tag in ['SuccessValue','SuccessReceiptId','Failure','Unknown'],'A receipt execution status is unsupported.')
  if tag in ['SuccessValue','SuccessReceiptId']:require(type(status[tag]) is str and len(status[tag])<=65536,'Receipt success data must be bounded text.')
  if tag=='Failure':require(type(status[tag]) is dict,'A failed receipt needs a structured failure reason.')
  if tag=='Unknown':complete=False
  if tag=='SuccessReceiptId' and status[tag] not in children:complete=False
  by_id[rid]=row
 # Child closure and reachability are checked independently of the top-level success result.
 seen=set();visiting=set();stack=[(txid,False)]
 while stack:
  rid,leaving=stack.pop()
  if leaving:visiting.remove(rid);seen.add(rid);continue
  if rid in visiting:raise ReviewError('The receipt graph contains a cycle.')
  if rid in seen:continue
  if rid not in by_id:complete=False;continue
  visiting.add(rid);stack.append((rid,True));stack.extend((c,False) for c in by_id[rid]['outcome']['receipt_ids'])
 if seen!=set(by_id):complete=False
 return txid,by_id,complete
def transfers(nodes,contract,vault,txid,base):
 events=[];complete=True;ignored=0
 for ni,(rid,row) in enumerate(nodes.items()):
  o=row['outcome'];success=next(iter(o['status'])) in ['SuccessReceiptId','SuccessValue']
  for li,line in enumerate(o['logs']):
   if not line.startswith('EVENT_JSON:'):continue
   if o['executor_id']!=contract or not success:ignored+=1;continue
   try:event=decode(line[len('EVENT_JSON:'):].encode())
   except ReviewError:complete=False;continue
   if type(event) is not dict or type(event.get('standard')) is not str:complete=False;continue
   if event['standard']!='nep141':continue
   if event.get('version')!='1.0.0' or event.get('event') not in ['ft_transfer','ft_mint','ft_burn']:complete=False;continue
   data=event.get('data')
   if type(data) is not list or not data or len(data)>1024:complete=False;continue
   for di,item in enumerate(data):
    try:
     require(type(item) is dict,'Event data is not an object.');a=amount(item.get('amount'),'Event amount');kind=event['event']
     old=account(item.get('old_owner_id')) if kind!='ft_mint' else None
     new=account(item.get('new_owner_id')) if kind!='ft_burn' else None
    except ReviewError:complete=False;continue
    # Mint/burn affect custody but are not payments; preserve them as distinct events.
    if old==vault or new==vault:
     events.append({'kind':kind,'amount':str(a),'old_owner_id':old,'new_owner_id':new,'receipt_id':rid,
      'transaction_id':txid,'log_index':li,'data_index':di,'source_pointer':base+('/transaction_outcome' if ni==0 else '/receipts_outcome/'+str(ni-1))+'/outcome/logs/'+str(li),'executor_id':o['executor_id']})
 return events,complete,ignored
def review(raw):
 d=decode(raw);obj(d,['format','id','network','source','scope','asset','vault','steps'],'Recording')
 require(d['format']==FORMAT,'This is not a token-recording-v1 file. Native bundles belong in the main workbench.')
 text(d['id'],'Recording ID',96);require(d['network'] in ['testnet','mainnet','sandbox'],'The recording must declare its network.')
 source=obj(d['source'],['kind','url','sha256','case_pointer','created_at'],'Source')
 require(source['kind'] in ['third-party-public-archive','synthetic-control','owner-recording'],'The source kind is unsupported.')
 text(source['url'],'Source URL',1024);hexhash(source['sha256']);text(source['case_pointer'],'Case pointer');text(source['created_at'],'Capture time')
 scope=obj(d['scope'],['single_owner_whole_vault','closed_intervals','meaning'],'Scope')
 require(all(type(scope[k]) is bool for k in ['single_owner_whole_vault','closed_intervals']),'Scope declarations must be true or false.')
 text(scope['meaning'],'Scope meaning',500)
 asset=obj(d['asset'],['standard','contract','sha256','code_hash','deployed_before','deployed_after'],'Asset')
 require(asset['standard']=='nep141','Only the recorded NEP-141 event format is supported.');account(asset['contract']);account(d['vault']);hexhash(asset['sha256'])
 require(asset['contract']!=d['vault'],'The token contract and custody vault must be separate accounts.')
 for k in ['code_hash','deployed_before','deployed_after']:text(asset[k],'Code identity',64)
 identity=len({asset['code_hash'],asset['deployed_before'],asset['deployed_after'],b58(bytes.fromhex(asset['sha256']))})==1
 require(type(d['steps']) is list and 0<len(d['steps'])<=64,'Choose a recording with 1 to 64 steps.')
 rows=[];all_tx=set();all_receipts=set();all_step=set();total_tx=0;total_logs=0
 for index,step in enumerate(d['steps']):
  obj(step,['id','operation','source_pointer','before','after','transactions'],'Step');sid=text(step['id'],'Step ID',96)
  require(sid not in all_step,'Step IDs must be unique.');all_step.add(sid)
  text(step['operation'],'Operation',64);text(step['source_pointer'],'Step source pointer')
  before=snapshot(step['before']);after=snapshot(step['after']);events=[];complete=True;ignored=0;reasons=[]
  if not identity:reasons.append('Reported token code identities disagree.')
  if not scope['single_owner_whole_vault'] or not scope['closed_intervals']:reasons.append('Single-owner or closed-interval assumptions have not been declared.')
  if step['before']['block_height']>=step['after']['block_height']:reasons.append('Endpoint block heights are not ordered.')
  require(type(step['transactions']) is list and len(step['transactions'])<=64,'A step contains too many transactions.')
  if not step['transactions']:complete=False
  for ti,tx in enumerate(step['transactions']):
   obj(tx,['source_pointer','result'],'Transaction');text(tx['source_pointer'],'Transaction source pointer')
   tid,nodes,closed=outcomes(tx['result']);require(tid not in all_tx,'The same transaction is assigned to multiple steps.');all_tx.add(tid)
   require(not all_receipts.intersection(nodes),'A receipt appears in multiple transactions.');all_receipts.update(nodes)
   total_tx+=1;total_logs+=sum(sum(len(x.encode('utf-8')) for x in n['outcome']['logs']) for n in nodes.values())
   require(total_tx<=256 and len(all_receipts)<=8192 and total_logs<=1024*1024,'The recording exceeds its transaction, receipt or log budget.')
   found,understood,n=transfers(nodes,asset['contract'],d['vault'],tid,tx['source_pointer']);events.extend(found);ignored+=n;complete=complete and closed and understood
  if not complete:reasons.append('The FINAL receipt graph or token-event interpretation is incomplete.')
  delta=after['held']-before['held'];rights=lambda s:s['credit']+s['pending']+s['reserved'];change=rights(after)-rights(before)
  if any(rights(s)!=s['liabilities'] for s in [before,after]):reasons.append('The reported total liability does not equal this single-owner ledger.')
  inbound=sum(int(e['amount']) for e in events if e['new_owner_id']==d['vault']);outbound=sum(int(e['amount']) for e in events if e['old_owner_id']==d['vault'])
  net=inbound-outbound;agrees=delta==net
  evidence='unknown' if reasons else 'agrees' if agrees else 'contradicts'
  reduction=max(0,delta-change) if evidence=='agrees' else None
  creation=max(0,change-delta) if evidence=='agrees' else None
  conservation='unknown' if evidence!='agrees' else 'reduced_without_payment' if reduction else 'increased_without_backing' if creation else 'preserved'
  backing='unknown' if reasons else 'insufficient' if any(s['held']<s['liabilities'] for s in [before,after]) else 'sufficient'
  conclusion='inconclusive' if reasons else 'recorded-inconsistency' if evidence=='contradicts' or conservation!='preserved' or backing=='insufficient' else 'recorded-consistent'
  rows.append({'id':sid,'operation':step['operation'],'source_pointer':step['source_pointer'],'before':step['before'],'after':step['after'],
   'held_delta':str(delta),'rights_delta':str(change),'gross_in':str(inbound),'gross_out':str(outbound),'event_net':str(net),
   'entitlement_reduction':str(reduction) if reduction is not None else None,'unfunded_rights':str(creation) if creation is not None else None,
   'state_event_agreement':evidence,'rights_conservation':conservation,'backing':backing,'conclusion':conclusion,
   'reasons':reasons,'events':events,'ignored_event_logs':ignored,'transaction_ids':[t['result']['transaction']['hash'] for t in step['transactions']]})
 conclusion='recorded-inconsistency' if any(r['conclusion']=='recorded-inconsistency' for r in rows) else 'inconclusive' if any(r['conclusion']=='inconclusive' for r in rows) else 'recorded-consistent'
 return {'format':REPORT,'recording_id':d['id'],'recording_sha256':sha256(raw).hexdigest(),'assessor_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
  'network':d['network'],'source':source,'asset':asset,'vault':d['vault'],'conclusion':conclusion,'steps':rows,'assumptions':ASSUMPTIONS,
  'meaning':'Conditional consistency of recorded custody and rights. Not an authorization verdict, authenticated chain observation, independent audit, or native financial gate.',
  'units':'Atomic token units; no ticker, decimal scaling, NEAR or USD conversion inferred.','new_model_calls':0,'new_transactions':0}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('recording',type=Path);a=p.parse_args()
 try:
  require(a.recording.stat().st_size<=MAX_BYTES,'The recording exceeds 2 MiB.');result=review(a.recording.read_bytes())
  print(pack(result).decode());return 0
 except (OSError,ValueError,TypeError,KeyError) as e:print(json.dumps({'error':str(e)[:300]}));return 2
if __name__=='__main__':raise SystemExit(main())
