"""Separate exact-integer reference for the registered unsigned-receipt profile.

This module executes no Rust, Wasm, model, network or original runtime oracle.
Its fee formula is source-informed, same-author and limited to one ordinary
FunctionCall action. It is not independent blind evaluation or authentication.
"""
from __future__ import annotations
import base64,json

class EvidenceError(ValueError):pass

def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise EvidenceError('Duplicate JSON field: '+k)
        out[k]=v
    return out

def strict_json(raw:bytes):
    def reject(value):raise EvidenceError('Non-integer JSON value: '+value)
    try:return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_float=reject,parse_constant=reject)
    except (UnicodeError,json.JSONDecodeError) as exc:raise EvidenceError('Invalid UTF-8 JSON') from exc

def natural(value,where,bits=128):
    if type(value) is int:n=value
    elif type(value) is str and value.isascii() and value.isdecimal() and len(value)<=39:
        n=int(value)
        if str(n)!=value:raise EvidenceError('Noncanonical decimal at '+where)
    else:raise EvidenceError('Unsigned integer required at '+where)
    if not 0<=n<2**bits:raise EvidenceError('Unsigned integer bound at '+where)
    return n

def prepaid_credit(method:str,args:bytes,gas,deposit,price,execution_costs):
    if type(method) is not str or type(args) is not bytes:raise EvidenceError('Exact method text/argument bytes required')
    try:method_raw=method.encode('utf-8')
    except UnicodeError as exc:raise EvidenceError('Invalid method Unicode') from exc
    g=natural(gas,'gas',64);d=natural(deposit,'deposit');p=natural(price,'price')
    if p==0:raise EvidenceError('Registered profile requires priced gas')
    fee={k:natural(execution_costs[k],'fee.'+k,64) for k in ['new_action_receipt','function_call_base','function_call_byte']}
    static=fee['new_action_receipt']+fee['function_call_base']+fee['function_call_byte']*(len(method_raw)+len(args))
    total_gas=g+static
    if total_gas>=2**64 or total_gas*p+d>=2**128:raise EvidenceError('Prepaid budget overflow')
    # Ordinary FunctionCall has zero prepaid inner-delegate send fees. Parent
    # send costs were paid outside this supplied-receipt accounting universe.
    return {'attached':g,'static_execution':static,'prepaid_send':0,'credit':total_gas*p+d}

def receipt_binding(receipt,call,current,price,execution_costs):
    if type(receipt) is not dict or receipt.get('receiver_id')!=current or receipt.get('predecessor_id')!=call['predecessor']:
        raise EvidenceError('Receipt actor/receiver binding differs')
    body=receipt.get('receipt',{}).get('Action')
    if type(body) is not dict or body.get('signer_id')!=call['signer']:
        raise EvidenceError('Expected original ordinary action receipt and signer binding')
    if body.get('input_data_ids')!=[] or body.get('output_data_receivers')!=[]:
        raise EvidenceError('Unexpected input/output data dependency in root receipt')
    actions=body.get('actions')
    if type(actions) is not list or len(actions)!=1 or type(actions[0]) is not dict or set(actions[0])!={'FunctionCall'}:
        raise EvidenceError('One ordinary FunctionCall action required')
    fn=actions[0]['FunctionCall']
    if fn.get('method_name')!=call['method']:raise EvidenceError('Method binding differs')
    try:args=base64.b64decode(fn['args'],validate=True)
    except (ValueError,TypeError,KeyError) as exc:raise EvidenceError('Invalid exact base64 argument bytes') from exc
    if args!=call['args_utf8'].encode('utf-8'):raise EvidenceError('Argument binding differs')
    for key in ['gas','deposit']:
        if natural(fn[key],key)!=natural(call[key],'input.'+key):raise EvidenceError('Call value binding differs: '+key)
    if natural(body['gas_price'],'receipt.price')!=natural(price,'input.price'):
        raise EvidenceError('Price binding differs')
    return prepaid_credit(call['method'],args,call['gas'],call['deposit'],price,execution_costs)

def total_accounts(snapshot):
    accounts=snapshot['accounts']
    if type(accounts) is not dict:raise EvidenceError('Account snapshot required')
    total=0
    for name,row in accounts.items():
        if row is None:continue
        total+=natural(row['amount'],'account.'+name+'.amount')+natural(row['locked'],'account.'+name+'.locked')
    return total

def closed_conservation(before,after,blocks,credit):
    if set(before['accounts'])!=set(after['accounts']):raise EvidenceError('Account universe differs')
    delta=total_accounts(after)-total_accounts(before);burnt=deficit=subsidized=0
    for block in blocks:
        if block.get('runtime_error') is not None:raise EvidenceError('Runtime error is not closed financial evidence')
        if type(block.get('signed_transactions')) is not int or block['signed_transactions']!=0:raise EvidenceError('Expected exact zero signed transaction count')
        b=block['balance_stats']
        burnt+=sum(natural(b[k],'burn.'+k) for k in ['tx_burnt','slashed_burnt','other_burnt'])
        deficit+=natural(b['gas_deficit'],'gas_deficit');subsidized+=natural(b['subsidized'],'subsidized')
    measured=delta+burnt-deficit-subsidized
    expected=natural(credit,'incoming credit')
    if measured!=expected:
        raise EvidenceError(f'Conservation differs: delta {delta} + burnt {burnt} - deficit {deficit} - subsidy {subsidized} = {measured}; incoming {expected}')
    return {'account_delta':str(delta),'burnt':str(burnt),'deficit':str(deficit),'subsidized':str(subsidized),'incoming_credit':str(expected),'matches':True}

def principal_delta(before,after,beneficiary):
    def amount(snapshot):
        row=snapshot['accounts'].get(beneficiary)
        return 0 if row is None else natural(row['amount'],'beneficiary amount')+natural(row['locked'],'beneficiary locked')
    if beneficiary not in before['accounts'] or beneficiary not in after['accounts']:
        raise EvidenceError('Beneficiary not observed; absence of observation is not zero payout')
    return amount(after)-amount(before)

def self_check():
    # Constructed arithmetic controls, not runtime traces or benchmark cases.
    fees={'new_action_receipt':'7','function_call_base':'11','function_call_byte':'2'}
    assert prepaid_credit('abc',b'{}',30,4,5,fees)=={'attached':30,'static_execution':28,'prepaid_send':0,'credit':294}
    assert prepaid_credit('é',b'{}',30,4,5,fees)['credit']==284 # UTF8 length 2, not one character.
    before={'accounts':{'a':{'amount':str(2**100),'locked':'3'},'merchant':None}}
    after={'accounts':{'a':{'amount':str(2**100+174),'locked':'3'},'merchant':{'amount':'100','locked':'0'}}}
    blocks=[{'signed_transactions':0,'balance_stats':{'tx_burnt':'20','slashed_burnt':'0','other_burnt':'0','gas_deficit':'0','subsidized':'0'}}]
    assert closed_conservation(before,after,blocks,294)['matches']
    assert principal_delta(before,after,'merchant')==100
    bad=0
    for operation in [lambda:natural(True,'bool'),lambda:natural('٠','unicode'),lambda:natural('01','leading'),lambda:strict_json(b'{"a":1,"a":2}'),lambda:strict_json(b'{"a":1.0}'),lambda:closed_conservation(before,after,blocks,293),lambda:principal_delta(before,after,'unobserved')]:
        try:operation()
        except EvidenceError:bad+=1
        else:raise AssertionError('Malformed arithmetic control accepted')
    return {'constructedArithmeticControlsPassed':True,'rejections':bad,'runtimeCasesValidated':0,'meaning':'Independent-module arithmetic and binding preflight only; source-informed same-author, no engine/model execution.'}

if __name__=='__main__':print(json.dumps(self_check()))
