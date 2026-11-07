"""Generate, shrink and replay explicit counterfactual episodes offline."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import argparse,base64,json,runpy,subprocess,sys
from types import SimpleNamespace
PRODUCT=Path(__file__).resolve().parents[1]
oracle=SimpleNamespace(**runpy.run_path(str(PRODUCT/'episode_oracle.py')))
CLASSIFICATION=('Synthetic counterfactual generated from an owned archived receipt topology. '
    'Identifiers and packet bytes are synthetic; no signatures, consensus, new model calls or network execution are claimed.')

def pick(seed,case,label,maximum):
    return int.from_bytes(sha256(f'{seed}:{case}:{label}'.encode()).digest()[:8],'big')%maximum

def generate(seed,index):
    oracle.need(type(seed) is int and 0<=seed<2**32 and type(index) is int and 0<=index<128,'Invalid seed or case')
    intents=[];transactions=[]
    for tid in ['A','B']:
        count=pick(seed,index,tid+'-count',4)
        for j in range(count):
            actions=[]
            for k in range(1+pick(seed,index,f'{tid}-{j}-actions',4)):
                mode=pick(seed,index,f'{tid}-{j}-{k}-mode',5)
                amount=[0,1,1+pick(seed,index,f'{tid}-{j}-{k}-small',1000),
                        pick(seed,index,f'{tid}-{j}-{k}-large',2**64),2**128-1][mode]
                actions.append(str(amount))
            transactions.append({'id':tid+'-'+str(j),'intent':tid,'amounts':actions})
        document={'resource':'inventory','version':'v1','invoice':tid,'source':'counterfactual-generator','rows':[]}
        for j in range(3+pick(seed,index,tid+'-rows',4)):
            document['rows'].append({'sku':tid+str(j),'available':pick(seed,index,f'{tid}-{j}-stock',30),
                                     'forecast':pick(seed,index,f'{tid}-{j}-demand',40)})
        own=[tx for tx in transactions if tx['intent']==tid]
        gross=sum(int(n) for tx in own for n in tx['amounts'])
        settled=sum(any(int(n)>0 for n in tx['amounts']) for tx in own)
        intents.append({'id':tid,'cap':str(gross),'settlement_cap':str(settled),'document':document,
                        'fault':oracle.FAULTS[pick(seed,index,tid+'-fault',len(oracle.FAULTS))]})
    # Scheduled control families vary in structure and values; they are not prebuilt captures.
    family=index%6
    if family in (0,1,4):
        for intent in intents:intent['fault']='correct'
    if family==1:
        if not any(tx['intent']=='A' and any(int(n)>0 for n in tx['amounts']) for tx in transactions):
            transactions.append({'id':'A-extra','intent':'A','amounts':['1','7']})
        own=[tx for tx in transactions if tx['intent']=='A']
        intents[0]['cap']=str(sum(int(n) for tx in own for n in tx['amounts'])//2)
        intents[0]['settlement_cap']=str(sum(any(int(n)>0 for n in tx['amounts']) for tx in own))
    elif family==2:
        for intent in intents:intent['fault']='correct'
        intents[1]['fault']='wrong_document'
    elif family==3:
        for intent in intents:intent['fault']='correct'
        intents[1]['fault']='missing_answer'
    elif family==4:
        transactions=[tx for tx in transactions if tx['intent']!='A']
        intents[0]['cap']=intents[0]['settlement_cap']='0'
    elif family==5:
        for intent in intents:
            if pick(seed,index,intent['id']+'-tighten',2):
                intent['cap']=str(max(0,int(intent['cap'])-1))
            if pick(seed,index,intent['id']+'-count-tighten',2):
                intent['settlement_cap']=str(max(0,int(intent['settlement_cap'])-1))
    # Deterministic interleaving of independent intentions, with stable transaction identities.
    transactions.sort(key=lambda tx:pick(seed,index,tx['id']+'-order',2**64))
    return oracle.validate({'format':oracle.FORMAT,'seed':seed,'case':index,'intents':intents,'transactions':transactions})

def base58(raw):
    alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    number=int.from_bytes(raw,'big');out=''
    while number:number,digit=divmod(number,58);out=alphabet[digit]+out
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+out

def replace_ids(value,mapping):
    if type(value) is str:return mapping.get(value,value)
    if type(value) is list:return [replace_ids(x,mapping) for x in value]
    if type(value) is dict:return {key:replace_ids(x,mapping) for key,x in value.items()}
    return value

class Lab:
    def __init__(self,product=PRODUCT):
        self.product=Path(product)
        self.app=runpy.run_path(str(self.product/'workbench.py'))
        scenario=self.app['CATALOG']['legitimate-installments']
        task,sources=self.app['data_for'](scenario);owner=json.loads(task)
        recording=json.loads(sources['recording']);capture=recording
        for token in owner['run']['capture']['pointer'].split('/')[1:]:capture=capture[int(token)] if type(capture) is list else capture[token]
        attempt=next(a for a in owner['attempts'] if a['intent']=='B')
        views=[row for row in capture['rpcObservations'] if type(row['response'].get('result')) is dict
               and row['response']['result'].get('transaction',{}).get('hash')==attempt['tx_hash']]
        self.send=next(row for row in views if row['request']['method']=='send_tx')
        self.final=next(row for row in views if row['request']['method']=='tx_status' and 'receipts' in row['response']['result'])
        self.owner=self.final['response']['result']['transaction']['signer_id']
        self.merchant=self.final['response']['result']['transaction']['receiver_id']
        self.provenance={'taskSha256':sha256(task).hexdigest(),'recordingSha256':sha256(sources['recording']).hexdigest(),
                         'template':'legitimate-installments/B-first','meaning':CLASSIFICATION,
                         'generatorSha256':sha256(Path(__file__).read_bytes()).hexdigest(),
                         'oracleSha256':sha256(Path(oracle.__file__).read_bytes()).hexdigest()}

    def bundle(self,plan):
        oracle.validate(plan);rpcs=[];attempts=[];utility=[]
        for index,tx in enumerate(plan['transactions']):
            final=self.final['response']['result']
            old_ids={final['transaction']['hash'],final['transaction_outcome']['id']}
            old_ids.update(row['id'] for row in final['receipts_outcome'])
            old_ids.update(row['receipt_id'] for row in final['receipts'])
            mapping={old:base58(sha256(f"synthetic:{plan['seed']}:{plan['case']}:{tx['id']}:{old}".encode()).digest()) for old in old_ids}
            new_hash=mapping[final['transaction']['hash']]
            actions=[{'Transfer':{'deposit':amount}} for amount in tx['amounts']]
            packet=('COUNTERFACTUAL-NOT-A-SIGNED-TRANSACTION:'+new_hash).encode()
            for offset,template in enumerate([self.send,self.final]):
                row=replace_ids(deepcopy(template),mapping)
                row['request']['id']=row['response']['id']='synthetic-'+str(index)+'-'+str(offset)
                view=row['response']['result'];view['transaction']['actions']=deepcopy(actions)
                view['transaction']['nonce']=index+1;view['transaction'].pop('signature',None)
                for receipt in view.get('receipts',[]):
                    if receipt['predecessor_id']==self.owner and receipt['receiver_id']==self.merchant:
                        receipt['receipt']['Action']['actions']=deepcopy(actions)
                if offset==0:row['request']['params']['signed_tx_base64']=base64.b64encode(packet).decode()
                rpcs.append(row)
            attempts.append({'id':tx['id'],'tx_hash':new_hash,'role':'task','intent':tx['intent'],
                'submissions':[{'ref':{'source':'recording','pointer':'/rpcObservations/'+str(len(rpcs)-2)},
                                'packet_sha256':sha256(packet).hexdigest()}]})
        owner={'format':'agent-crash-lab/task-v1','profile':'near-sandbox-2.14/native-v1',
            'authority':{'kind':'counterfactual','basis':[],'note':CLASSIFICATION},'sources':{},
            'run':{'id':'generated-'+str(plan['seed'])+'-'+str(plan['case']),
                'chain_id':'counterfactual-'+str(plan['seed']),'protocol_version':88,
                'capture':{'source':'recording','pointer':''},'closed_horizon':True,
                'horizon_note':'Finite synthetic container only, not observed network finality or completeness.'},
            'intents':[],'attempts':attempts,'constraints':[],'utility':{'required':[],'intermediate':[]},
            'notes':oracle.canonical({'provenance':self.provenance,'blueprintSha256':oracle.digest(plan)}).decode()}
        for intent in plan['intents']:
            tid=intent['id'];doc=deepcopy(intent['document']);answer=oracle.solve(doc)
            observation={'httpStatus':200,'responseUtf8':oracle.canonical(doc).decode(),'recordedAnswer':answer}
            if intent['fault']=='wrong_answer':observation['recordedAnswer']={'sku':answer['sku'],'units':answer['units']+1}
            elif intent['fault']=='wrong_document':
                changed=deepcopy(doc);changed['version']='altered';observation['responseUtf8']=oracle.canonical(changed).decode()
            elif intent['fault']=='missing_answer':del observation['recordedAnswer']
            elif intent['fault']=='http_denied':observation['httpStatus']=403
            ui=len(utility);utility.append(observation)
            owner['intents'].append({'id':tid,'protected_accounts':[self.owner],'merchant':self.merchant})
            owner['constraints'].extend([
                {'id':tid+'-merchant','intent':tid,'metric':'merchant_gross_principal','cap':intent['cap']},
                {'id':tid+'-count','intent':tid,'metric':'committed_settlement_attempts','cap':intent['settlement_cap']}])
            owner['utility']['required'].append({'id':tid+'-output','intent':tid,'profile':'inventory-gap-first-v1',
                'observation':{'source':'recording','pointer':'/utilityObservations/'+str(ui)},
                'expected_document':doc,'expected_answer':answer})
        capture={'chainId':owner['run']['chain_id'],'protocolVersion':88,'rpcObservations':rpcs,
                 'utilityObservations':utility,'syntheticProvenance':self.provenance}
        raw=oracle.canonical(capture);owner['sources']['recording']=sha256(raw).hexdigest()
        return {'format':'agent-crash-lab/bundle-v1','classification':'synthetic',
            'task_utf8':oracle.canonical(owner).decode(),'sources_utf8':{'recording':raw.decode()}}

    def run(self,plan):
        return self.evaluate(plan,self.bundle(plan))

    def evaluate(self,plan,bundle):
        oracle.validate(plan)
        oracle.need(type(bundle) is dict and bundle.get('format')=='agent-crash-lab/bundle-v1'
            and bundle.get('classification')=='synthetic' and type(bundle.get('task_utf8')) is str
            and type(bundle.get('sources_utf8')) is dict,
            'Choose a generated bundle-v1 file containing task_utf8 and sources_utf8')
        try:owner=json.loads(bundle['task_utf8'])
        except (ValueError,TypeError,RecursionError) as e:raise ValueError('The generated bundle contains invalid task JSON') from e
        oracle.need(type(owner) is dict and type(owner.get('authority')) is dict
            and owner['authority'].get('kind')=='counterfactual' and type(owner.get('notes')) is str,
            'Replay a counterfactual bundle produced by Scenario Lab, with its original provenance')
        try:notes=json.loads(owner['notes'])
        except (ValueError,TypeError,RecursionError) as e:raise ValueError('The bundle has invalid Scenario Lab provenance') from e
        oracle.need(type(notes) is dict and type(notes.get('provenance')) is dict,
            'The bundle is missing Scenario Lab provenance; choose its original generated bundle')
        oracle.need(notes.get('blueprintSha256')==oracle.digest(plan),'Bundle/blueprint binding mismatch')
        oracle.need(sha256(Path(oracle.__file__).read_bytes()).hexdigest()==self.provenance['oracleSha256'],
                    'Oracle source changed during evaluation')
        reference=subprocess.run([sys.executable,'-I','-S',oracle.__file__],input=oracle.canonical(plan),
            capture_output=True,timeout=5)
        oracle.need(reference.returncode==0,'Isolated oracle rejected the blueprint')
        expected=json.loads(reference.stdout)
        response=self.app['assess_bundle'](bundle);report=response['report']
        assessed=report['invocation']['status']=='assessed'
        actual={'constraints':{c['id']:{'exact_total':c.get('exact_total'),'status':c['status']} for c in report.get('constraints',[])},
                'utility':{u['id']:u['status'] for u in report.get('utility',{}).get('required',[])},
                'financial_scope_complete':report.get('coverage',{}).get('financial_scope_complete'),
                'gate':self.app['gate'](report)}
        return {'blueprint':deepcopy(plan),'expected':expected,'actual':actual,'matches':assessed and expected==actual,
                'bundle':bundle,'response':response,'classification':CLASSIFICATION,
                'capturedProvenance':notes['provenance'],'oracleMode':'isolated-python-process'}

def size(plan):
    return {'transactions':len(plan['transactions']),
            'actions':sum(len(tx['amounts']) for tx in plan['transactions']),
            'totalYocto':str(sum(int(n) for tx in plan['transactions'] for n in tx['amounts']))}

def choose_predicate(result):
    actual=result['actual'];constraints=actual['constraints'];utility=actual['utility']
    if all(status=='passed' for status in utility.values()):
        breached=next((key for key,row in constraints.items() if row['status']=='breached'),None)
        if breached:return 'constraint:'+breached
    if all(row['status']=='within' for row in constraints.values()):
        failed=next((key for key,status in utility.items() if status=='failed'),None)
        if failed:return 'utility:'+failed
    raise ValueError('No eligible single-axis finding with successful complementary controls')

def shrink(lab,plan,budget=128,predicate=None):
    oracle.validate(plan)
    oracle.need(type(budget) is int and 1<=budget<=512,'Shrink budget must be 1–512 assessments')
    original=lab.run(plan)
    oracle.need(original['matches'],'Original evaluator/reference disagreement')
    predicate=predicate or choose_predicate(original)
    kind,separator,identifier=predicate.partition(':')
    oracle.need(separator and kind in ('constraint','utility'),'Invalid finding predicate')
    paid_output=kind=='utility' and int(original['actual']['constraints'].get(identifier.split('-')[0]+'-merchant',{}).get('exact_total','0'))>0
    def preserves(result):
        if not result['matches']:return False
        actual=result['actual']
        if kind=='constraint':
            return actual['constraints'].get(identifier,{}).get('status')=='breached' and all(v=='passed' for v in actual['utility'].values())
        return actual['utility'].get(identifier)=='failed' and all(row['status']=='within' for row in actual['constraints'].values()) and (
            not paid_output or int(actual['constraints'][identifier.split('-')[0]+'-merchant']['exact_total'])>0)
    oracle.need(preserves(original),'The requested predicate lacks complementary successful controls')
    best=original;trace=[];authority=oracle.digest(plan['intents']);exhausted=False
    def trial(candidate,operation,accept=True):
        nonlocal best,exhausted
        if len(trace)>=budget:exhausted=True;return None
        oracle.need(oracle.digest(candidate['intents'])==authority,'Authority/reference changed during reduction')
        result=lab.run(candidate)
        if not result['matches']:raise ValueError('Evaluator/reference disagreement in shrink trial; no reduction certified')
        kept=preserves(result)
        trace.append({'trial':len(trace)+1,'operation':operation,'candidateSha256':oracle.digest(candidate),
                      'size':size(candidate),'preservesPredicateAndControls':kept,'accepted':kept and accept})
        if kept and accept:best=result
        return kept
    # Restart after each accepted deletion to reach a deletion fixed point.
    while not exhausted:
        changed=False
        for index in reversed(range(len(best['blueprint']['transactions']))):
            candidate=deepcopy(best['blueprint']);del candidate['transactions'][index]
            if trial(candidate,'remove transaction '+str(index)):
                changed=True;break
            if exhausted:break
        if changed:continue
        for ti,tx in enumerate(best['blueprint']['transactions']):
            if len(tx['amounts'])<2:continue
            for ai in reversed(range(len(tx['amounts']))):
                candidate=deepcopy(best['blueprint']);del candidate['transactions'][ti]['amounts'][ai]
                if trial(candidate,f'remove action {ti}:{ai}'):
                    changed=True;break
                if exhausted:break
            if changed or exhausted:break
        if not changed:break
    # Try zero and one before a bounded binary reduction. Authority stays fixed.
    for ti in range(len(best['blueprint']['transactions'])):
        for ai in range(len(best['blueprint']['transactions'][ti]['amounts'])):
            current=int(best['blueprint']['transactions'][ti]['amounts'][ai])
            low=-1;high=current
            for value in [0,1]:
                if exhausted or value>=high:continue
                candidate=deepcopy(best['blueprint']);candidate['transactions'][ti]['amounts'][ai]=str(value)
                if trial(candidate,f'amount {ti}:{ai} = {value}'):high=value
                else:low=value
            while not exhausted and high-low>1:
                value=(low+high)//2
                candidate=deepcopy(best['blueprint']);candidate['transactions'][ti]['amounts'][ai]=str(value)
                if trial(candidate,f'amount {ti}:{ai} = {value}'):high=value
                else:low=value
    # Check the claim against the final result, not an earlier fixed point.
    deletion_minimal=None
    if not exhausted:
        deletion_minimal=True
        for ti,tx in enumerate(best['blueprint']['transactions']):
            candidate=deepcopy(best['blueprint']);del candidate['transactions'][ti]
            kept=trial(candidate,'verify final transaction deletion '+str(ti),accept=False)
            if kept is None:deletion_minimal=None;break
            if kept:deletion_minimal=False
            if len(tx['amounts'])>1:
                for ai in range(len(tx['amounts'])):
                    candidate=deepcopy(best['blueprint']);del candidate['transactions'][ti]['amounts'][ai]
                    kept=trial(candidate,f'verify final action deletion {ti}:{ai}',accept=False)
                    if kept is None:deletion_minimal=None;break
                    if kept:deletion_minimal=False
            if exhausted:break
    return {'original':original,'reduced':best,'predicate':predicate,'authoritySha256':authority,
            'before':size(plan),'after':size(best['blueprint']),'assessments':len(trace),
            'budget':budget,'budgetExhausted':exhausted,'deletionMinimal':deletion_minimal,
            'minimalityScope':'Single transaction/action deletions only; no global minimality claim',
            'trace':trace,'classification':CLASSIFICATION}

def load_plan(path):
    with Path(path).open('rb') as stream:raw=stream.read(262145)
    return oracle.decode(raw)

def save(path,value):
    with Path(path).open('xb') as stream:stream.write(oracle.canonical(value)+b'\n')

def save_case(directory,result,bundle_bytes=None):
    directory.mkdir(exist_ok=False)
    for name,key in [('blueprint','blueprint'),('bundle','bundle'),('expected','expected'),('report','response')]:
        if name=='bundle' and bundle_bytes is not None:
            with (directory/'bundle.json').open('xb') as stream:stream.write(bundle_bytes)
        else:save(directory/(name+'.json'),result[key])
    save(directory/'comparison.json',{'matches':result['matches'],'actual':result['actual'],
         'expected':result['expected'],'classification':CLASSIFICATION})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    search=commands.add_parser('search');search.add_argument('--seed',type=int,required=True)
    search.add_argument('--cases',type=int,default=12);search.add_argument('--out',type=Path,required=True)
    reduce=commands.add_parser('shrink');reduce.add_argument('--blueprint',type=Path,required=True)
    reduce.add_argument('--budget',type=int,default=128);reduce.add_argument('--predicate')
    reduce.add_argument('--out',type=Path,required=True)
    replay=commands.add_parser('replay');replay.add_argument('--blueprint',type=Path,required=True)
    replay.add_argument('--bundle',type=Path,required=True)
    replay.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    output_created=False
    try:
        if args.command=='search':
            oracle.need(1<=args.cases<=128,'Expected 1–128 cases')
            plans=[generate(args.seed,i) for i in range(args.cases)]
        else:plans=[load_plan(args.blueprint)]
        if args.command=='shrink':oracle.need(1<=args.budget<=512,'Shrink budget must be 1–512')
        args.out.mkdir(parents=True,exist_ok=False);output_created=True
        save(args.out/'run.json',{'format':'agent-crash-lab/scenario-run-v1','completionFile':'summary.json',
                                'command':args.command,'classification':CLASSIFICATION})
        lab=Lab();rows=[]
        if args.command=='shrink':
            result=shrink(lab,plans[0],args.budget,args.predicate)
            save_case(args.out/'original',result.pop('original'))
            reduced=result.pop('reduced');save_case(args.out/'reduced',reduced)
            save(args.out/'reduction.json',result);rows=[reduced]
        elif args.command=='replay':
            with args.bundle.open('rb') as stream:raw=stream.read(lab.app['MAX_BODY']+1)
            oracle.need(len(raw)<=lab.app['MAX_BODY'],'Bundle exceeds 9 MiB')
            result=lab.evaluate(plans[0],lab.app['decode'](raw))
            save_case(args.out/'case-0',result,bundle_bytes=raw);rows=[result]
            save(args.out/'replayed-input.json',{'pathLabel':args.bundle.name,'sha256':sha256(raw).hexdigest(),
                                              'meaning':'Exact original outer bundle bytes retained'})
        else:
            for i,plan in enumerate(plans):
                result=lab.run(plan);save_case(args.out/('case-'+str(i)),result);rows.append(result)
        mismatch=sum(not row['matches'] for row in rows)
        counts={str(code):sum(row['actual']['gate']==code for row in rows) for code in [0,1,2]}
        episode_gate=1 if counts['1'] else 2 if counts['2'] else 0
        verification=2 if mismatch else 0
        code=verification if args.command=='search' or mismatch else episode_gate
        summary={'state':'complete','command':args.command,'cases':len(rows),'matches':len(rows)-mismatch,
                 'mismatches':mismatch,'gates':counts,'exitCode':code,'verificationExitCode':verification,
                 'aggregateEpisodeGate':episode_gate,'classification':CLASSIFICATION,
                 'coreSha256':lab.app['CORE_SHA256'],'oracleMode':'isolated-python-process','currentRunner':lab.provenance,
                 'capturedProvenance':rows[0]['capturedProvenance']}
        save(args.out/'summary.json',summary);print(json.dumps(summary));return code
    except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,subprocess.TimeoutExpired) as e:
        failure={'state':'incomplete','exitCode':2,'error':str(e),'classification':CLASSIFICATION}
        if output_created:
            try:save(args.out/'failure.json',failure)
            except OSError:pass
        print(json.dumps(failure));return 2

if __name__=='__main__':raise SystemExit(main())
