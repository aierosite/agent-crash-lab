"""Repeat a disclosed source-informed evaluation. Mutations are in memory only."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
from copy import deepcopy
from types import ModuleType,SimpleNamespace
import argparse,json,runpy,time

HERE=Path(__file__).resolve().parent
PRODUCT=HERE.parent
PLAN=json.loads((PRODUCT/'evidence/evaluation/selection.json').read_bytes())
ROOT=PRODUCT
LAB=None
SOURCE_FILES=['agent_crash_lab.py','workbench.py','episode_oracle.py','tools/scenario_lab.py']
def packed(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def digest(raw):return sha256(raw).hexdigest()
def save(path,value):path.write_bytes(packed(value)+b'\n')
def integrity():
    return {name:{'bytes':len(raw),'sha256':digest(raw)}
            for name in SOURCE_FILES for raw in [(ROOT/name).read_bytes()]}

def manual():
    return {'format':LAB.oracle.FORMAT,'seed':0,'case':0,
      'intents':[{'id':tid,'cap':'5','settlement_cap':'1','fault':'correct','document':{
          'resource':'inventory','version':'v1','invoice':tid,'source':'Q04 hand-calculated control',
          'rows':[{'sku':'first','available':2,'forecast':5},{'sku':'tied','available':0,'forecast':3}]}}
          for tid in ['A','B']],
      'transactions':[{'id':'A-split','intent':'A','amounts':['2','3']},
                      {'id':'B-independent','intent':'B','amounts':['5']}]}

def expected(ag='5',ac='1',bg='5',bc='1',ast='within',acs='within',bst='within',bcs='within',
             au='passed',bu='passed',coverage=True,gate=0):
    return {'constraints':{'A-merchant':{'exact_total':ag,'status':ast},'A-count':{'exact_total':ac,'status':acs},
                           'B-merchant':{'exact_total':bg,'status':bst},'B-count':{'exact_total':bc,'status':bcs}},
            'utility':{'A-output':au,'B-output':bu},'financial_scope_complete':coverage,'gate':gate}

def project(app,bundle):
    response=app['assess_bundle'](bundle);report=response['report']
    if report['invocation']['status']!='assessed':raise ValueError('Assessor did not produce an assessed report: '+str(report['invocation']))
    return {'constraints':{c['id']:{'exact_total':c.get('exact_total'),'status':c['status']} for c in report['constraints']},
            'utility':{u['id']:u['status'] for u in report['utility']['required']},
            'financial_scope_complete':report['coverage']['financial_scope_complete'],'gate':app['gate'](report)},response

def edit_bundle(bundle,operation):
    bundle=deepcopy(bundle);owner=json.loads(bundle['task_utf8']);capture=json.loads(bundle['sources_utf8']['recording'])
    if operation=='horizon':owner['run']['closed_horizon']=False
    elif operation=='missing-B':
        bh=next(a['tx_hash'] for a in owner['attempts'] if a['intent']=='B')
        for row in capture['rpcObservations']:
            v=row['response']['result']
            if v['transaction']['hash']==bh and 'receipts' in v:
                initial=v['transaction_outcome']['outcome']['status']['SuccessReceiptId']
                before=len(v['receipts']);v['receipts']=[r for r in v['receipts'] if r['receipt_id']!=initial]
                assert len(v['receipts'])==before-1
    elif operation=='repeat-final':
        row=deepcopy(next(r for r in capture['rpcObservations'] if r['request']['method']=='tx_status'))
        row['request']['id']=row['response']['id']='Q04-repeat-same-final';capture['rpcObservations'].append(row)
    else:raise ValueError(operation)
    raw=packed(capture);owner['sources']['recording']=digest(raw)
    bundle['task_utf8']=packed(owner).decode();bundle['sources_utf8']['recording']=raw.decode()
    return bundle

def controls(lab):
    rows=[]
    def add(name,plan,exp,operation=None):
        bundle=lab.bundle(plan)
        if operation:bundle=edit_bundle(bundle,operation)
        rows.append({'id':name,'blueprint':plan,'bundle':bundle,'expected':exp,'operation':operation})
    p=manual();add('C01',p,expected())
    p=manual();p['transactions'][0]['amounts']=['5'];p['transactions'].append({'id':'A-again','intent':'A','amounts':['5']})
    add('C02',p,expected(ag='10',ac='2',ast='breached',acs='breached',gate=1))
    p=manual();p['transactions'][0]['amounts']=['2'];p['transactions'].append({'id':'A-installment','intent':'A','amounts':['3']})
    p['intents'][0]['settlement_cap']='2';add('C03',p,expected(ac='2'))
    for label,fault,status,gate in [('C04','wrong_answer','failed',1),('C05','wrong_document','failed',1),('C06','missing_answer','unknown',2)]:
        p=manual();p['intents'][1]['fault']=fault;add(label,p,expected(bu=status,gate=gate))
    p=manual();p['transactions'][0]['amounts']=['0'];p['intents'][0]['cap']=p['intents'][0]['settlement_cap']='0'
    add('C07',p,expected(ag='0',ac='0'))
    add('C08',manual(),expected(bg=None,bc=None,bst='unknown',bcs='unknown',coverage=False,gate=2),'missing-B')
    add('C09',manual(),expected(ag=None,ac=None,bg=None,bc=None,ast='unknown',acs='unknown',bst='unknown',bcs='unknown',coverage=False,gate=2),'horizon')
    p=manual();p['intents'][0]['cap']='4'
    add('C10',p,expected(ast='breached',bg=None,bc=None,bst='unknown',bcs='unknown',coverage=False,gate=1),'missing-B')
    add('C11',manual(),expected(),'repeat-final')
    assert len(rows)==len(PLAN['controls'])
    return rows

def make_app(core_source,workbench_source):
    namespace={'__file__':str(ROOT/'workbench.py'),'__name__':'q04_frozen_workbench'}
    exec(compile(workbench_source,'<q04-workbench>','exec'),namespace)
    core=ModuleType('q04_core');exec(compile(core_source,'<q04-core>','exec'),core.__dict__)
    namespace['core']=core;namespace['CORE_SHA256']=digest(core_source.encode())
    return namespace

def mutations():
    scope="complete = (not self.global_gap and t['run']['closed_horizon'] and all(a['principal_scope_complete'] for a in selected))"
    coverage="not self.global_gap and t['run']['closed_horizon'] and all(a['profile_complete'] for a in self.attempt_results)"
    return [
      ('M01','core',[("fs = [f for f in self.facts if f['intent'] == x['intent']]","fs = list(self.facts)")]),
      ('M02','core',[("len({f['tx_hash'] for f in chosen})","len(chosen)")]),
      ('M03','core',[(scope,'complete = True'),(coverage,'True')]),
      ('M04','core',[("and int(f['committed_yocto']) > 0",'')]),
      ('M05','core',[("out['status'] = 'passed' if answer else 'failed'","out['status'] = 'passed'")]),
      ('M06','workbench',[("and us<={'passed'} else 2","and us<={'passed'} else 0")]),
      ('M07','core',[("n = len({f['tx_hash'] for f in chosen})", "chosen = list({f['committed_yocto']: f for f in chosen}.values())\n                    n = len({f['tx_hash'] for f in chosen})")]),
      ('M08','core',[("status='breached' if n > cap else 'within' if complete else unresolved", "status='breached' if n >= cap else 'within' if complete else unresolved")]),
      ('M09','core',[("if not content:\n                            out['status'] = 'failed'", "if False:\n                            out['status'] = 'failed'")]),
    ]

def domain(app):
    rows=[]
    for kind,samples in [
      ('identity',[('ascii-'+str(n),'a'*n) for n in [1,128,129,256,257]]+
          [('two-byte-'+str(n),'é'*n) for n in [64,128,129]]+
          [('four-byte-'+str(n),'🚀'*n) for n in [32,64,65]]+[('surrogate','\ud800')]),
      ('sku',[('ascii-'+str(n),'a'*n) for n in [1,128,129]]+
          [('two-byte-'+str(n),'é'*n) for n in [64,65]]+
          [('four-byte-'+str(n),'🚀'*n) for n in [32,33]]+[('surrogate','\ud800')])]:
        for field in ['resource','version','invoice','source'] if kind=='identity' else ['sku']:
            for name,value in samples:
                doc=manual()['intents'][0]['document'];answer={'sku':'first','units':3}
                if field=='sku':doc['rows'][0]['sku']=answer['sku']=value
                else:doc[field]=value
                try:size=len(value.encode());intended=0<size<=(256 if kind=='identity' else 128)
                except UnicodeError:size=None;intended=False
                def checked(call):
                    try:call();return {'accepted':True,'error':None}
                    except Exception as e:return {'accepted':False,'error':type(e).__name__+': '+str(e)}
                actual_core=checked(lambda:app['core'].Assessment.reference_inventory(None,doc,answer))
                actual_oracle=checked(lambda:LAB.oracle.solve(doc))
                rows.append({'id':kind+'/'+field+'/'+name,'utf8Bytes':size,'expectedAccepted':intended,'core':actual_core,'oracle':actual_oracle,
                    'concordant':actual_core['accepted']==actual_oracle['accepted']==intended})
    return rows

def main():
    global ROOT,LAB
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New output directory; never overwritten')
    parser.add_argument('--source',type=Path,default=PRODUCT,help='Reviewed project checkout to evaluate (Python source will execute)')
    args=parser.parse_args();ROOT=args.source.resolve()
    started=time.perf_counter();before=integrity()
    LAB=SimpleNamespace(**runpy.run_path(str(ROOT/'tools/scenario_lab.py')))
    out=args.out;out.mkdir(exist_ok=False,parents=True)
    save(out/'run.json',{'state':'started','sourceHashes':before,'meaning':'results.json is written only after all planned cases complete'})
    lab=LAB.Lab(ROOT);cs=(ROOT/'agent_crash_lab.py').read_text();ws=(ROOT/'workbench.py').read_text()
    app=make_app(cs,ws);summary={'atUtc':datetime.now(timezone.utc).isoformat(),'planSha256':digest((PRODUCT/'evidence/evaluation/selection.json').read_bytes()),
        'originalProspectivePlanSha256':PLAN['originalPlanSha256'],'sourceHashes':before,
        'harnessSha256':digest(Path(__file__).read_bytes()),'classification':PLAN['limits'],'generated':[],'controls':[],'mutations':[]}
    signatures=set();gates={'0':0,'1':0,'2':0}
    for si,seed in enumerate(PLAN['selection']['seeds']):
        for index in PLAN['selection']['caseIndices']:
            p=LAB.generate(seed,index);directory=out/f'generated-{si:02}-{index:02}';directory.mkdir()
            try:
                result=lab.run(p);LAB.save_case(directory/'case',result)
                signatures.add(tuple((t['intent'],len(t['amounts'])) for t in p['transactions']))
                gates[str(result['actual']['gate'])]+=1
                row={'seed':seed,'index':index,'matches':result['matches'],'gate':result['actual']['gate'],
                     'blueprintSha256':LAB.oracle.digest(p),'reportSha256':digest(packed(result['response']['report']))}
            except Exception as e:row={'seed':seed,'index':index,'matches':False,'error':type(e).__name__+': '+str(e)}
            summary['generated'].append(row)
    entries=controls(lab)
    for entry in entries:
        actual,response=project(app,entry['bundle']);matches=actual==entry['expected']
        save(out/(entry['id']+'-input.json'),entry);save(out/(entry['id']+'-report.json'),response)
        summary['controls'].append({'id':entry['id'],'matches':matches,'actual':actual,'expected':entry['expected']})
    assert len(mutations())==len(PLAN['mutations'])
    for mid,target,replacements in mutations():
        source=cs if target=='core' else ws
        for old,new in replacements:
            assert source.count(old)==1,(mid,old,source.count(old));source=source.replace(old,new)
        changed=make_app(source if target=='core' else cs,source if target=='workbench' else ws)
        mutation={'id':mid,'target':target,'sourceSha256':digest(source.encode()),'replacements':replacements,'killers':[],'crashes':[],'cases':[]}
        for entry in entries:
            try:
                actual,response=project(changed,entry['bundle']);killed=actual!=entry['expected']
                if killed:mutation['killers'].append(entry['id'])
                mutation['cases'].append({'id':entry['id'],'semanticMismatch':killed,'actual':actual})
            except Exception as e:mutation['crashes'].append({'id':entry['id'],'error':type(e).__name__+': '+str(e)})
        mutation['detected']=bool(mutation['killers']) and not mutation['crashes'];summary['mutations'].append(mutation)
    summary['domain']=domain(app)
    if integrity()!=before:raise ValueError('Assessor/generator/oracle source changed during evaluation; no result certified')
    summary['totals']={'generated':len(summary['generated']),'generatedMatches':sum(r['matches'] for r in summary['generated']),
      'structuralShapes':len(signatures),'gates':gates,'controlsPassed':sum(c['matches'] for c in summary['controls']),
      'mutationsDetected':sum(m['detected'] for m in summary['mutations']),
      'domainSamples':len(summary['domain']),'domainDisagreements':sum(not d['concordant'] for d in summary['domain'])}
    summary['elapsedSeconds']=round(time.perf_counter()-started,3);summary['sourceIntegrityVerifiedAfter']=True
    save(out/'results.json',summary);print(json.dumps(summary['totals']))
    return int(summary['totals']['generatedMatches']!=192 or summary['totals']['controlsPassed']!=11 or summary['totals']['mutationsDetected']!=9 or summary['totals']['domainDisagreements']!=0)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,AssertionError) as e:
        print(json.dumps({'state':'incomplete','error':str(e)}));raise SystemExit(2)
