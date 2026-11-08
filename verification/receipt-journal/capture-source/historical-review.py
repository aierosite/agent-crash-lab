"""Finite unsigned native-receipt journal review. Data only, no execution or RPC.

The policy is explicit caller intent. This checks supplied local-runtime evidence,
not chain authenticity, signatures, arbitrary callbacks or overall agent safety.
The evaluator is same-author/source-informed, not an independent blind audit.
"""
from pathlib import Path
from hashlib import sha256
import base64,json,re,runpy

_ref=runpy.run_path(str(Path(__file__).resolve().with_name('financial_reference.py')))
EvidenceError=_ref['EvidenceError'];load=_ref['strict_json'];number=_ref['natural']
_account=re.compile(r'(?=.{2,64}\Z)[a-z0-9]+(?:[-_.][a-z0-9]+)*\Z')
_alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def require(ok,message):
    if not ok:raise EvidenceError(message)

def zero(value):return type(value) is int and value==0

def identity(text):
    require(type(text) is str and 32<=len(text)<=44,'Invalid receipt/state identity')
    n=0
    for c in text:
        require(c in _alphabet,'Invalid base58 identity');n=n*58+_alphabet.index(c)
    raw=n.to_bytes((n.bit_length()+7)//8,'big')
    raw=b'\0'*(len(text)-len(text.lstrip('1')))+raw
    require(len(raw)==32,'Identity is not32bytes');return text

def encode_hash(raw):
    n=int.from_bytes(raw,'big');out=''
    while n:n,r=divmod(n,58);out=_alphabet[r]+out
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+out

def snapshot(value,observed):
    require(type(value) is dict and set(value)=={'state_root','accounts','contract_data_hex'},'Unsupported snapshot')
    identity(value['state_root']);require(type(value['accounts']) is dict and set(value['accounts'])==set(observed),'Snapshot account universe differs')
    _ref['total_accounts'](value)
    for name,row in value['accounts'].items():
        require(_account.fullmatch(name) is not None,'Invalid observed account')
        if row is not None:
            require(type(row) is dict and set(row)=={'amount','locked','storage_usage','contract'},'Malformed account observation')
            number(row['storage_usage'],'storage_usage',64);require(type(row['contract']) is str,'Contract kind required')
    require(type(value['contract_data_hex']) is dict,'Contract data required')
    for key,data in value['contract_data_hex'].items():
        for raw in [key,data]:
            if raw is not None:require(type(raw) is str and len(raw)%2==0 and re.fullmatch('[0-9a-f]*',raw) is not None,'Invalid raw storage hex')
    return value

def action(receipt):
    require(type(receipt) is dict and set(receipt)=={'predecessor_id','receiver_id','receipt_id','receipt'},'Malformed receipt envelope')
    identity(receipt['receipt_id'])
    require(all(type(receipt[k]) is str and _account.fullmatch(receipt[k]) for k in ['predecessor_id','receiver_id']),'Invalid receipt account')
    variants=receipt['receipt'];require(type(variants) is dict and len(variants)==1,'One receipt variant required')
    kind,body=next(iter(variants.items()));require(kind in ['Action','ActionV2'] and type(body) is dict,'Only ordinary native action receipts supported')
    expected={'actions','gas_price','input_data_ids','output_data_receivers','signer_id','signer_public_key'}|({'refund_to'} if kind=='ActionV2' else set())
    require(set(body)==expected,'Unsupported action receipt fields')
    require(body.get('refund_to') is None and body['input_data_ids']==body['output_data_receivers']==[],'Data dependencies/custom refunds are outside this native profile')
    require(type(body['signer_id']) is str and _account.fullmatch(body['signer_id']),'Invalid original signer context')
    require(body['signer_public_key']=='ed25519:11111111111111111111111111111111','Unsigned fixture public context required')
    number(body['gas_price'],'receipt.gas_price')
    values=body['actions'];require(type(values) is list and len(values)==1 and type(values[0]) is dict and len(values[0])==1,'One native action required')
    tag,payload=next(iter(values[0].items()));require(tag in ['FunctionCall','Transfer'] and type(payload) is dict,'Unsupported action')
    if tag=='Transfer':require(set(payload)=={'deposit'},'Unsupported native transfer');number(payload['deposit'],'transfer.deposit')
    return tag,payload,body

def parse(raw):
    require(type(raw) is bytes and 0<len(raw)<=4_194_304,'Journal must be bounded nonempty bytes')
    lines=raw.splitlines(keepends=True);torn=not raw.endswith(b'\n')
    if torn:lines=lines[:-1]
    require(0<len(lines)<=512,'No complete records or too many journal records')
    events=[]
    for i,line in enumerate(lines):
        require(line.endswith(b'\n') and line.strip(),'Empty or unterminated middle record')
        e=load(line);require(type(e) is dict and set(e)=={'sequence','event','data'},'Malformed journal record')
        require(type(e['sequence']) is int and e['sequence']==i,'Journal sequence gap/reorder/boolean')
        require(type(e['event']) is str and type(e['data']) is dict,'Malformed event/data');events.append(e)
    return events,torn

def review(raw,policy):
    require(type(policy) is dict and set(policy)=={'format','case','step','payer','beneficiary','required_atomic','max_gross_atomic','scope'},'Explicit finite native-payment policy required')
    require(policy['format']=='agent-crash-lab/unsigned-native-payment-intent-v1','Unsupported intent format')
    require(type(policy['step']) is int and 0<=policy['step']<20,'Invalid intended step')
    for k in ['payer','beneficiary']:require(type(policy[k]) is str and _account.fullmatch(policy[k]),'Invalid policy account')
    require(policy['payer']!=policy['beneficiary'],'Self-transfer is outside the merchant profile')
    required=number(policy['required_atomic'],'required_atomic');cap=number(policy['max_gross_atomic'],'max_gross_atomic');require(0<required<=cap,'Invalid principal obligation')
    events,torn=parse(raw);first=events[0];require(first['event']=='run_start','Missing run_start')
    start=first['data'];require(set(start)=={'raw_input_utf8','configuration','signed_transactions'} and zero(start['signed_transactions']),'Invalid unsigned run header')
    require(type(start['raw_input_utf8']) is str and len(start['raw_input_utf8'].encode())<=1_048_576,'Missing exact raw input')
    inputs=load(start['raw_input_utf8'].encode());require(type(inputs) is dict and set(inputs)=={'cases'} and type(inputs['cases']) is list and 0<len(inputs['cases'])<=8,'Invalid input cases')
    specs=inputs['cases'];require(len({c['id'] for c in specs})==len(specs),'Duplicate case identity')
    target_spec=next((c for c in specs if c['id']==policy['case']),None);require(target_spec is not None,'Intent case is not in the bound input')
    require(target_spec['current']==policy['payer'] and policy['step']<len(target_spec['calls']),'Intent payer/step differs')
    configuration=start['configuration'];require(type(configuration) is dict and configuration.get('protocol')==88 and configuration.get('vm_kind')=='Wasmtime','Unsupported runtime configuration')
    require(number(target_spec['gas_price'],'case.gas_price')>=number(configuration['min_gas_purchase_price'],'minimum gas price')>0,'Unpriced receipt input')
    current=None;cursor=0;completed=[];target=None;full=False;fault=None;global_ids=set()
    for e in events[1:]:
        kind=e['event'];d=e['data']
        require(not full and fault is None,'Record after terminal run/fault marker')
        if kind=='case_begin':
            require(current is None and cursor<len(specs) and d=={'case':specs[cursor]['id']},'Case order differs')
            spec=specs[cursor];require(len(spec['observe'])==len(set(spec['observe'])) and len(spec['observe'])<=16,'Invalid observation universe')
            require(set(a['id'] for a in spec['accounts']).issubset(spec['observe']),'Seeded account omitted from financial universe')
            current={'spec':spec,'initial':None,'snapshot':None,'steps':[],'active':None,'height':1};continue
        if kind=='run_complete':
            require(set(d)=={'format','upstream_revision','runtime','configuration','context','signed_transactions','cases'},'Unsupported whole-report fields')
            require(current is None and cursor==len(specs) and d.get('cases')==completed,'Whole report/case journal mismatch')
            require(d.get('configuration')==configuration and zero(d.get('signed_transactions')) and d.get('format')=='agent-crash-lab/unsigned-receipt-research-v1','Whole report header mismatch')
            require(d['upstream_revision']=='bc4e9e8cfb03d9e82f027883055624e18576993e' and d['runtime']=='node-runtime Runtime::apply','Runtime source claim differs')
            full=True;continue
        require(current is not None,'Event outside a case');spec=current['spec'];active=current['active']
        if kind=='case_initialized':
            require(current['initial'] is None and d.get('case')==spec['id'] and set(d)=={'case','code_hash','initial'},'Duplicate/mismatched genesis capture')
            identity(d['code_hash']);snap=snapshot(d['initial'],spec['observe'])
            seeded={a['id']:a for a in spec['accounts']}
            for name,row in snap['accounts'].items():
                if name not in seeded:require(row is None,'Unseeded genesis account appears')
                else:require(row is not None and number(row['amount'],'genesis amount')==number(seeded[name]['balance'],'input balance') and number(row['locked'],'genesis locked')==number(seeded[name]['locked'],'input locked'),'Genesis balance differs')
            current.update(initial=snap,snapshot=snap,code_hash=d['code_hash']);continue
        require(current['initial'] is not None,'Missing initialized state')
        if kind=='step_begin':
            require(active is None and d.get('case')==spec['id'] and d.get('index')==len(current['steps']),'Step order differs')
            i=d['index'];require(type(i) is int and i<len(spec['calls']),'Invalid step index');call=spec['calls'][i]
            require(d.get('label')==call['label'] and d.get('before')==current['snapshot'],'Step state/label differs')
            receipt=d['input_receipt'];tag,_,_=action(receipt);require(tag=='FunctionCall','Root must be FunctionCall')
            require(receipt['receipt_id']==encode_hash(sha256(f"{spec['id']}:{i}:{call['label']}".encode()).digest()),'Root receipt identity differs')
            credit=_ref['receipt_binding'](receipt,call,spec['current'],spec['gas_price'],configuration['execution_gas_costs'])
            require(number(d['external_incoming_prepaid_credit'],'incoming credit')==credit['credit'],'Prepaid credit differs')
            require(receipt['receipt_id'] not in global_ids,'Reused root identity');global_ids.add(receipt['receipt_id'])
            active={'index':i,'call':call,'root':receipt,'before':d['before'],'blocks':[],'pending':[receipt],'begin':None,'credit':credit,'parents':{},'outcomes':{},'receipts':{receipt['receipt_id']:receipt},'queue_unknown':True,'queue_remaining':False,'result':None}
            current['active']=active
            if spec['id']==policy['case'] and i==policy['step']:target=active
            continue
        if kind=='case_result':
            require(set(d)=={'id','code_hash','initial','steps_planned','steps_executed','steps','final','validator_context','signed_transactions','access_keys_seeded'},'Unsupported case-report fields')
            require(active is None and d.get('id')==spec['id'],'Case result while a step is open')
            require(d.get('initial')==current['initial'] and d.get('final')==current['snapshot'] and d.get('code_hash')==current['code_hash'],'Case snapshot/code differs')
            require(d.get('steps')==current['steps'] and type(d.get('steps_executed')) is int and d['steps_executed']==len(current['steps']) and d.get('steps_planned')==len(spec['calls']),'Case steps differ')
            require(zero(d.get('signed_transactions')) and zero(d.get('access_keys_seeded')),'Unexpected signed transactions/access keys')
            validator=d.get('validator_context');require(type(validator) is dict and validator.get('account')==spec['validator'],'Validator context differs')
            seeded_validator=next((a for a in spec['accounts'] if a['id']==spec['validator']),None)
            require(seeded_validator is not None and number(validator['stake'],'validator stake')==number(seeded_validator['locked'],'declared fixture stake')>0,'Validator stake differs')
            completed.append(d);current=None;cursor+=1;continue
        require(active is not None,'Block/event without active step')
        if kind=='block_begin':
            require(active['begin'] is None and d.get('case')==spec['id'] and d.get('step')==active['index'],'Invalid block begin')
            require(type(d.get('round')) is int and d['round']==len(active['blocks']) and d.get('height')==current['height'],'Block round/height differs')
            require(d.get('state_root_before')==current['snapshot']['state_root'] and d.get('incoming')==active['pending'] and zero(d.get('signed_transactions')),'Incoming queue/state differs')
            active['begin']=d;continue
        if kind=='block_result':
            require(active['begin'] is not None and d.get('case')==spec['id'] and d.get('step')==active['index'],'Unbound block result');row=d['result'];begin=active['begin']
            for k in ['round','height','state_root_before','incoming']:require(row.get(k)==begin[k],'Block capture mismatch: '+k)
            require(zero(row.get('signed_transactions')),'Unexpected transactions');snap=snapshot(row['snapshot_after'],spec['observe']);require(row['state_root_after']==snap['state_root'],'After root differs')
            outgoing=row['outgoing'];outcomes=row['outcomes'];require(type(outgoing) is list and type(outcomes) is list,'Missing full receipts/outcomes')
            incoming={r['receipt_id']:r for r in row['incoming']};require(len(incoming)==len(row['incoming']),'Duplicate incoming identity')
            observed={o['id']:o['outcome'] for o in outcomes};require(len(observed)==len(outcomes) and set(observed)==set(incoming),'Missing/duplicate receipt outcome')
            children={r['receipt_id']:r for r in outgoing};require(len(children)==len(outgoing),'Duplicate outgoing identity');emitted=[]
            for rid,receipt in incoming.items():
                _,_,_=action(receipt);o=observed[rid];require(o.get('executor_id')==receipt['receiver_id'],'Outcome executor differs')
                status=o.get('status');require(type(status) is dict and len(status)==1 and next(iter(status)) in ['SuccessValue','Failure'],'Only terminal ordinary-native outcomes supported')
                require(rid not in active['outcomes'],'Receipt executed twice');active['outcomes'][rid]=o
                require(type(o.get('receipt_ids')) is list,'Missing outgoing identities')
                for child_id in o['receipt_ids']:
                    identity(child_id);require(child_id in children and child_id not in active['parents'],'Unbound/repeated causal child');active['parents'][child_id]=rid;emitted.append(child_id)
            require(len(emitted)==len(children) and set(emitted)==set(children),'Outgoing receipt/causal link differs')
            for rid,receipt in children.items():
                require(rid not in global_ids,'Receipt identity reused');global_ids.add(rid);tag,_,_=action(receipt);require(tag=='Transfer','Cross-contract callbacks are outside the finite native profile')
                require(receipt['receiver_id'] in spec['observe'],'Unobserved native recipient');active['receipts'][rid]=receipt
            delayed=number(row['delayed_receipts'],'delayed_receipts',64);queued_bytes=row.get('congestion_receipt_bytes')
            if queued_bytes is not None:queued_bytes=number(queued_bytes,'congestion_receipt_bytes')
            flag=row.get('internal_queue_remaining_after');require(type(flag) is bool and flag==(delayed>0 or (queued_bytes is not None and queued_bytes>0)),'Raw/derived internal queue differs')
            require(type(row['balance_stats']) is dict and set(row['balance_stats'])=={'tx_burnt','slashed_burnt','other_burnt','gas_deficit','subsidized'},'Unsupported balance-statistic fields')
            for value in row['balance_stats'].values():number(value,'balance statistic')
            active.update(pending=outgoing,begin=None,queue_unknown=queued_bytes is None,queue_remaining=flag)
            active['blocks'].append(row);current['snapshot']=snap;current['height']+=1;continue
        if kind=='step_result':
            require(active['begin'] is None and d.get('case')==spec['id'] and active['blocks'],'Step closes an unobserved block')
            complete=not active['pending'] and not active['queue_remaining'];credit=active['credit']
            expected={'index':active['index'],'label':active['call']['label'],'input_receipt':active['root'],'external_incoming_prepaid_credit':str(credit['credit']),'budget_gas':{k:str(credit[k]) for k in ['attached','prepaid_send','static_execution']},'before':active['before'],'blocks':active['blocks'],'after':current['snapshot'],'pending_receipts':active['pending'],'internal_queue_remaining':active['queue_remaining'],'complete':complete,'runtime_error':None}
            require(d.get('result')==expected,'Full step result differs from observed blocks')
            if complete:_ref['closed_conservation'](active['before'],current['snapshot'],active['blocks'],credit['credit'])
            active['result']=expected;current['steps'].append(expected);current['active']=None;continue
        if kind=='research_fault_checkpoint':
            require(active['begin'] is None and active['blocks'],'Fault marker without a synced block')
            require(d=={'case':spec['id'],'step':active['index'],'round':active['blocks'][-1]['round'],'mode':'sync_data_then_cooperative_pause_for_external_sigkill'},'Fault marker mismatch');fault=d;continue
        raise EvidenceError('Unsupported event: '+kind)
    if target is None or not target['blocks']:
        return {'required_payment_gate':2,'payment_status':'unknown','operation_closed':False,'whole_run_complete':full and not torn,'evidence':'Intended receipt execution not observed','torn_tail':torn}
    payer=policy['payer'];beneficiary=policy['beneficiary'];paid=committed=0;failed=[];violations=[];refunds=[];root_id=target['root']['receipt_id']
    for rid,receipt in target['receipts'].items():
        tag,body,context=action(receipt)
        if rid==root_id:continue
        parent_id=target['parents'].get(rid);require(parent_id in target['receipts'],'Missing native receipt parent');parent=target['receipts'][parent_id]
        o=target['outcomes'].get(rid)
        if receipt['predecessor_id']==payer:
            require(parent_id==root_id and tag=='Transfer','Unexpected principal transfer ancestry');amount=number(body['deposit'],'principal amount');committed+=amount
            if receipt['receiver_id']!=beneficiary:violations.append({'kind':'recipient-outside-intent','receipt_id':rid})
            if o is not None:
                if 'Failure' in o['status']:failed.append(rid)
                elif receipt['receiver_id']==beneficiary:paid+=amount
        elif receipt['predecessor_id']=='system':
            require(tag=='Transfer' and number(context['gas_price'],'refund price')==0,'Malformed system refund')
            if parent_id==root_id:
                require(receipt['receiver_id']==target['root']['receipt']['Action']['signer_id'],'Gas refund recipient differs')
                require(context['signer_id']==target['root']['receipt']['Action']['signer_id'],'Gas refund signer differs')
            else:
                parent_tag,parent_body,_=action(parent);parent_outcome=target['outcomes'].get(parent_id)
                require(parent_tag=='Transfer' and parent_outcome is not None and 'Failure' in parent_outcome['status'],'Principal refund lacks failed transfer')
                require(receipt['receiver_id']==parent['predecessor_id'] and context['signer_id']=='system' and number(body['deposit'],'refund amount')==number(parent_body['deposit'],'failed transfer amount'),'Principal refund binding differs')
                refunds.append({'receipt_id':rid,'amount':body['deposit'],'status':'pending' if o is None else ('settled' if 'SuccessValue' in o['status'] else 'failed')})
        else:raise EvidenceError('Unknown native transfer actor')
    if committed>cap:violations.append({'kind':'gross-principal-cap-exceeded','committed':str(committed),'cap':str(cap)})
    after=target['blocks'][-1]['snapshot_after'];delta=_ref['principal_delta'](target['before'],after,beneficiary)
    require(delta==paid,'Recipient balance and successful receipt principal disagree')
    closed=target['begin'] is None and not target['pending'] and not target['queue_remaining'] and not target['queue_unknown']
    if closed:_ref['closed_conservation'](target['before'],after,target['blocks'],target['credit']['credit'])
    if paid>=required:payment='settled'
    elif failed or closed:payment='failed'
    else:payment='unknown'
    gate=1 if violations or payment=='failed' else (0 if payment=='settled' and closed else 2)
    root_outcome=target['outcomes'].get(root_id);root_status='unobserved' if root_outcome is None else ('failure' if 'Failure' in root_outcome['status'] else 'success')
    return {'format':'agent-crash-lab/local-native-journal-review-v1','required_payment_gate':gate,'payment_status':payment,'root_status':root_status,'principal_committed':str(committed),'principal_received':str(paid),'beneficiary_delta':str(delta),'failed_principal_receipts':failed,'principal_refunds':refunds,'violations':violations,'operation_closed':closed,'pending_receipt_ids':[r['receipt_id'] for r in target['pending']],'internal_queue_remaining':target['queue_remaining'],'queue_observation_missing':target['queue_unknown'],'whole_run_complete':full and not torn,'torn_tail':torn,'complete_records':len(events),'fault_checkpoint':fault,'scope':'Explicit one-root unsigned local native-transfer profile. Payment state is separate from transcript completion, useful work, retry authorization, signatures and authentic chain history.'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('journal',type=Path);p.add_argument('policy',type=Path);a=p.parse_args()
    try:r=review(a.journal.read_bytes(),load(a.policy.read_bytes()));print(json.dumps(r));raise SystemExit(r['required_payment_gate'])
    except (OSError,ValueError,KeyError,TypeError) as exc:print(json.dumps({'rejected':True,'error':str(exc)}));raise SystemExit(2)
