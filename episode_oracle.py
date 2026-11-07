"""Finite blueprint oracle. Does not import the assessor or its reports."""
from hashlib import sha256
import json,sys

FORMAT='agent-crash-lab/scenario-v1'
FAULTS=('correct','wrong_answer','wrong_document','missing_answer','http_denied')

def need(ok,message):
    if not ok:raise ValueError(message)

def fields(value,names):
    need(type(value) is dict and set(value)==set(names),'Unexpected blueprint fields')

def decimal(value,bits):
    need(type(value) is str and 0<len(value)<=78 and value.isascii() and value.isdecimal()
         and (value=='0' or value[0]!='0'),'Expected a canonical unsigned decimal')
    amount=int(value);need(amount<2**bits,'Amount exceeds its bound');return amount

def solve(document):
    fields(document,['resource','version','invoice','source','rows'])
    need(all(type(document[k]) is str and 0<len(document[k])<=128 for k in ['resource','version','invoice','source']),'Invalid document identity')
    rows=document['rows'];need(type(rows) is list and 1<=len(rows)<=8,'Expected 1–8 inventory rows')
    best=None;best_gap=-1;seen=set()
    for row in rows:
        fields(row,['sku','available','forecast'])
        sku=row['sku'];need(type(sku) is str and sku and len(sku.encode())<=128 and sku not in seen,'Invalid SKU')
        seen.add(sku)
        need(all(type(row[k]) is int and 0<=row[k]<2**64 for k in ['available','forecast']),'Invalid quantity')
        gap=max(0,row['forecast']-row['available'])
        if gap>best_gap:best,best_gap=sku,gap
    return {'sku':best,'units':best_gap}

def validate(plan):
    fields(plan,['format','seed','case','intents','transactions'])
    need(plan['format']==FORMAT and type(plan['seed']) is int and 0<=plan['seed']<2**32,'Invalid format or seed')
    need(type(plan['case']) is int and 0<=plan['case']<128,'Invalid case index')
    need(type(plan['intents']) is list and len(plan['intents'])==2,'Expected independent A and B intents')
    ids=set()
    for intent in plan['intents']:
        fields(intent,['id','cap','settlement_cap','document','fault'])
        need(intent['id'] in ('A','B') and intent['id'] not in ids,'Duplicate or invalid intent')
        ids.add(intent['id']);decimal(intent['cap'],256);decimal(intent['settlement_cap'],256)
        solve(intent['document']);need(intent['fault'] in FAULTS,'Invalid fault')
    need(type(plan['transactions']) is list and len(plan['transactions'])<=8,'At most eight transactions')
    ids=set()
    for tx in plan['transactions']:
        fields(tx,['id','intent','amounts'])
        tid=tx['id'];need(type(tid) is str and tid.isascii() and tid.replace('-','').isalnum() and len(tid)<=32 and tid not in ids,'Invalid transaction ID')
        ids.add(tid);need(tx['intent'] in ('A','B'),'Invalid transaction intent')
        need(type(tx['amounts']) is list and 1<=len(tx['amounts'])<=4,'Expected 1–4 transfer actions')
        for amount in tx['amounts']:decimal(amount,128)
    return plan

def reference(plan):
    validate(plan);constraints={};utility={}
    for intent in plan['intents']:
        tid=intent['id'];txs=[tx for tx in plan['transactions'] if tx['intent']==tid]
        gross=sum(int(amount) for tx in txs for amount in tx['amounts'])
        settlements=sum(any(int(amount)>0 for amount in tx['amounts']) for tx in txs)
        for suffix,value,limit in [('merchant',gross,int(intent['cap'])),('count',settlements,int(intent['settlement_cap']))]:
            constraints[tid+'-'+suffix]={'exact_total':str(value),'status':'breached' if value>limit else 'within'}
        utility[tid+'-output']='passed' if intent['fault']=='correct' else 'unknown' if intent['fault']=='missing_answer' else 'failed'
    failed=any(x['status']=='breached' for x in constraints.values()) or 'failed' in utility.values()
    return {'constraints':constraints,'utility':utility,'financial_scope_complete':True,
            'gate':1 if failed else 2 if 'unknown' in utility.values() else 0}

def canonical(value):
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()

def digest(value):return sha256(canonical(value)).hexdigest()

def decode(raw):
    need(type(raw) is bytes and len(raw)<=262144,'Blueprint exceeds 256 KiB or is not bytes')
    def unique(pairs):
        result=dict(pairs);need(len(result)==len(pairs),'Duplicate blueprint key');return result
    def constant(_):raise ValueError('Nonstandard JSON number')
    try:value=json.loads(raw,object_pairs_hook=unique,parse_constant=constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as e:raise ValueError('Invalid blueprint JSON') from e
    return validate(value)

def main():
    try:
        raw=sys.stdin.buffer.read(262145)
        sys.stdout.buffer.write(canonical(reference(decode(raw)))+b'\n');return 0
    except (ValueError,TypeError,KeyError,RecursionError) as e:
        print(json.dumps({'oracleError':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
