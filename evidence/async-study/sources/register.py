"""Register source-informed cases before inspecting their results; no assessor execution."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import base64,json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent/'product'
FROZEN=HERE/'baseline';FROZEN.mkdir(exist_ok=False)
for name in ['agent_crash_lab.py','workbench.py','RELEASE_MANIFEST.json']:(FROZEN/name).write_bytes((ROOT/name).read_bytes())
def pack(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def save(path,value):path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(pack(value)+b'\n')
def identity(label):
    raw=sha256(label.encode()).digest();number=int.from_bytes(raw,'big');alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';text=''
    while number:number,digit=divmod(number,58);text=alphabet[digit]+text
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+text
OWNER='owner.async-lab.near';VAULT='vault.async-lab.near';MERCHANT='merchant.async-lab.near'
KEY='ed25519:'+'1'*32
def outcome(rid,executor,children,status,block):
    return {'id':rid,'block_hash':block,'outcome':{'executor_id':executor,'receipt_ids':children,'status':status,
                                                 'gas_burnt':0,'tokens_burnt':'0','logs':[]}}
def receipt(rid,predecessor,receiver,actions):
    return {'receipt_id':rid,'predecessor_id':predecessor,'receiver_id':receiver,'receipt':{'Action':{
        'signer_id':OWNER,'signer_public_key':KEY,'gas_price':'0','input_data_ids':[],
        'output_data_receivers':[],'actions':actions}}}
def graph(plan,view,intent):
    label=plan['id']+'-'+intent;txid=identity(label+'-tx');initial=identity(label+'-initial')
    leafids=[identity(label+'-leaf-'+str(i)) for i in range(2)]
    function=[{'FunctionCall':{'method_name':'counterfactual_fanout','args':'e30=','gas':30000000000000,'deposit':'0'}}]
    transfer=[{'Transfer':{'deposit':'3'}}]
    actions=function if intent=='A' else transfer
    receiver=VAULT if intent=='A' else MERCHANT
    tx={'hash':txid,'signer_id':OWNER,'receiver_id':receiver,'public_key':KEY,'nonce':1 if intent=='A' else 2,'actions':actions}
    root=outcome(txid,OWNER,[initial],{'SuccessReceiptId':initial},identity(label+'-rootblock'))
    initialbody=receipt(initial,OWNER,receiver,actions)
    childlist=leafids if intent=='A' else []
    outcomes=[outcome(initial,receiver,childlist,{'SuccessValue':''},identity(label+'-initialblock'))]
    bodies=[initialbody]
    if intent=='A':
        for leaf in view['leaves']:
            amount=plan['amounts'][leaf]+int(plan['family']=='conflicting-leaf' and view.get('altered',False))
            outcomes.append(outcome(leafids[leaf],MERCHANT,[],{'SuccessValue':''},identity(label+'-leafblock-'+str(leaf))))
            bodies.append(receipt(leafids[leaf],VAULT,MERCHANT,[{'Transfer':{'deposit':str(amount)}}]))
    return {'status':{'SuccessValue':''},'transaction':tx,'transaction_outcome':root,'receipts_outcome':outcomes,
            'receipts':bodies,'final_execution_status':'FINAL' if view['wholeFinal'] else 'INCLUDED_FINAL'}
def bundle(plan,variant):
    rpcs=[];attempts=[];anchors=[]
    def rpc(method,params,result):
        index=len(rpcs);tag='synthetic-'+str(index)
        rpcs.append({'request':{'jsonrpc':'2.0','id':tag,'method':method,'params':params},
                     'response':{'jsonrpc':'2.0','id':tag,'result':result}})
        return {'source':'recording','pointer':'/rpcObservations/'+str(index)}
    for intent in ['A','B']:
        packet=('COUNTERFACTUAL-NOT-SIGNED:'+plan['id']+intent).encode()
        submission=rpc('send_tx',{'signed_tx_base64':base64.b64encode(packet).decode(),'wait_until':'NONE'},
                       {'final_execution_status':'NONE'})
        views=plan['views'] if intent=='A' else [{'leaves':[],'wholeFinal':True}]
        if variant=='reversed':views=list(reversed(views))
        if variant=='duplicated':views=[v for view in views for v in [view,view]]
        for view in views:
            data=graph(plan,view,intent)
            rpc('tx_status',{'tx_hash':data['transaction']['hash'],'sender_account_id':OWNER,'wait_until':'NONE'},data)
        attempts.append({'id':intent+'-attempt','tx_hash':identity(plan['id']+'-'+intent+'-tx'),'role':'task','intent':intent,
                         'submissions':[{'ref':submission,'packet_sha256':sha256(packet).hexdigest()}]})
    for leaf in plan['anchoredLeaves']:
        anchors.append(rpc('block',{'finality':'final'},{'header':{'hash':identity(plan['id']+'-A-leafblock-'+str(leaf))}}))
    document={'resource':'inventory','version':'v1','invoice':'A','source':'declared-local-reference',
              'rows':[{'sku':'item','available':0,'forecast':1}]}
    observations=[{'httpStatus':200,'responseUtf8':pack(document).decode(),'recordedAnswer':{'sku':'item','units':1}} for _ in range(2)]
    capture={'chainId':'counterfactual-async-'+plan['id'],'protocolVersion':88,'rpcObservations':rpcs,'utilityObservations':observations,
             'syntheticProvenance':'Constructed partial projections; not observed network execution or signed transactions.'}
    source={'recording':pack(capture),'basis':pack(plan)}
    owner={'format':'agent-crash-lab/task-v1','profile':'near-sandbox-2.14/native-v1',
           'authority':{'kind':'counterfactual','basis':[{'source':'basis','pointer':''}],
             'note':'Source-informed constructed asynchronous observations. Final heads are declared synthetic evidence, not authenticated chain proofs.'},
           'sources':{name:sha256(raw).hexdigest() for name,raw in source.items()},
           'run':{'id':plan['id'],'chain_id':capture['chainId'],'protocol_version':88,'capture':{'source':'recording','pointer':''},
                  'closed_horizon':plan['closedHorizon'],'horizon_note':'Finite constructed capture; complete exact totals require explicit whole-FINAL context.',
                  'final_block_refs':anchors},
           'intents':[{'id':intent,'protected_accounts':[OWNER,VAULT],'merchant':MERCHANT} for intent in ['A','B']],
           'attempts':attempts,'constraints':[
               {'id':intent+suffix,'intent':intent,'metric':metric,'cap':str(cap)}
               for intent in ['A','B'] for suffix,metric,cap in [('-merchant','merchant_gross_principal',plan['cap'] if intent=='A' else 3),
                                                               ('-count','committed_settlement_attempts',1)]],
           'utility':{'required':[{'id':intent+'-output','intent':intent,'profile':'inventory-gap-first-v1',
                                  'observation':{'source':'recording','pointer':'/utilityObservations/'+str(i)},
                                  'expected_document':document,'expected_answer':{'sku':'item','units':1}}
                                 for i,intent in enumerate(['A','B'])],'intermediate':[]}}
    return {'format':'agent-crash-lab/bundle-v1','task_utf8':pack(owner).decode(),
            'sources_utf8':{name:raw.decode() for name,raw in source.items()},'classification':'synthetic'}
families={
    'complementary-final-heads':([{'leaves':[0],'wholeFinal':False},{'leaves':[1],'wholeFinal':False}],[0,1],True),
    'single-final-head':([{'leaves':[0],'wholeFinal':False},{'leaves':[1],'wholeFinal':False}],[0],True),
    'no-final-heads':([{'leaves':[0],'wholeFinal':False},{'leaves':[1],'wholeFinal':False}],[],True),
    'same-leaf-repeated':([{'leaves':[0],'wholeFinal':False},{'leaves':[0],'wholeFinal':False}],[0],True),
    'growing-partial':([{'leaves':[0],'wholeFinal':False},{'leaves':[0,1],'wholeFinal':False}],[0,1],True),
    'whole-final':([{'leaves':[0],'wholeFinal':False},{'leaves':[0,1],'wholeFinal':True}],[],True),
    'open-horizon':([{'leaves':[0],'wholeFinal':False},{'leaves':[0,1],'wholeFinal':True}],[],False),
    'conflicting-leaf':([{'leaves':[0],'wholeFinal':False},{'leaves':[0],'wholeFinal':False,'altered':True}],[0],True)}
numbers={'zero':([0,0],0),'tight':([6,2],5),'allowed':([3,2],5),'u128':([2**128-1,1],2**128-1)}
plans=[];files={}
for family,(views,anchors,closed) in families.items():
    for number,(amounts,cap) in numbers.items():
        plan={'id':family+'-'+number,'family':family,'amounts':amounts,'cap':cap,'views':views,
              'anchoredLeaves':anchors,'closedHorizon':closed}
        plans.append(plan);save(HERE/'plans'/(plan['id']+'.json'),plan)
        for variant in ['original','reversed','duplicated']:
            path=HERE/'bundles'/(plan['id']+'-'+variant+'.json');save(path,bundle(plan,variant))
            files[path.relative_to(HERE).as_posix()]=sha256(path.read_bytes()).hexdigest()
record={'format':'agent-crash-lab/async-study-registration-v1','registeredAtUtc':datetime.now(timezone.utc).isoformat(),
        'baseRelease':'v0.8.0','baseCoreSha256':sha256((FROZEN/'agent_crash_lab.py').read_bytes()).hexdigest(),
        'requirements':['Order and duplicate-observation invariant financial projections','Union of unique independently finalized effects as a lower bound',
            'Unanchored partial observations cannot prove committed amounts','Partial evidence cannot prove exact total or clean gate',
            'Full FINAL and closed horizon can complete the supported profile','Conflicting A identity must not contaminate independent B',
            'Zero and u128 boundary amounts without floating-point conversion'],
        'primarySources':[{'url':'https://docs.near.org/api/rpc/transactions','readAtUtc':datetime.now(timezone.utc).isoformat(),
            'derivedFacts':['NONE may acknowledge without a hash or execution view','INCLUDED_FINAL does not assert receipt completion',
                            'FINAL includes refund completion','tx_status receipt bodies may be incomplete'],
            'interpretation':'Complementary partial captures are a constructed input family, not a claim these exact payloads were observed from a node.'}],
        'failedResearchAttempts':['Two older transaction-execution documentation URLs were unavailable.',
            'GitHub API nearcore tag lookup timed out; no source revision or conclusion is attributed to it.'],
        'planCount':len(plans),'correlatedBundleCount':len(files),'plans':plans,'bundles':files,
        'sources':{name:sha256((HERE/name).read_bytes()).hexdigest() for name in ['register.py','async_reference.py']},
        'scope':'Prospective source-informed same-author synthetic study. Not unseen external authorship, native execution or an accuracy estimate.'}
save(HERE/'registration.json',record)
print(json.dumps({'registered':True,'plans':len(plans),'correlatedBundles':len(files),
                  'registrationSha256':sha256((HERE/'registration.json').read_bytes()).hexdigest(),'assessorInvocationsBeforeRegistration':0}))
