"""Bind actual raw model outputs to explicitly synthetic native-effect inputs."""
from pathlib import Path
from hashlib import sha256
from types import SimpleNamespace
import json,runpy,subprocess,sys

HERE=Path(__file__).resolve().parent
def pack(x):return json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def save(p,x):p.write_bytes(pack(x)+b'\n')
def project(app,report):
    return {'constraints':{x['id']:{'exact_total':x.get('exact_total'),'status':x['status']} for x in report['constraints']},
      'utility':{x['id']:x['status'] for x in report['utility']['required']},
      'financial_scope_complete':report['coverage']['financial_scope_complete'],'gate':app['gate'](report)}

def main():
    plan_path=Path(sys.argv[1]);directory=Path(sys.argv[2]);out=Path(sys.argv[3])
    plan_raw=plan_path.read_bytes();plan=json.loads(plan_raw);root=Path(plan['baseRoot'])
    manifest_raw=(root/'RELEASE_MANIFEST.json').read_bytes()
    assert sha256(manifest_raw).hexdigest()==plan['baseManifestSha256']
    for name,expected in json.loads(manifest_raw)['files'].items():
        raw=(root/name).read_bytes();assert {'bytes':len(raw),'sha256':sha256(raw).hexdigest()}==expected,name
    for name,expected in plan['sources'].items():assert sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    reference=subprocess.run([sys.executable,'-I','-S',str(HERE/'proposal_oracle.py'),str(plan_path),str(directory)],capture_output=True,timeout=15)
    assert reference.returncode==0,reference.stdout.decode()+reference.stderr.decode()
    independent=json.loads(reference.stdout);assert len(independent['cases'])==16
    module=SimpleNamespace(**runpy.run_path(str(root/'tools/scenario_lab.py')));lab=module.Lab(root)
    out.mkdir(exist_ok=False,parents=True);rows=[];calls_raw=(directory/'calls.json').read_bytes();execution_raw=(directory/'execution.json').read_bytes()
    for item in independent['cases']:
        case=plan['cases'][item['case']];index=item['case']*2+(item['policy']=='guarded')
        blueprint={'format':module.oracle.FORMAT,'seed':case['seed'],'case':index,
          'intents':[{'id':tid,'cap':str(case['capCents']*10**22),'settlement_cap':'1','fault':'correct',
                      'document':case['expectedDocuments'][tid]} for tid in ['A','B']],
          'transactions':item['transactions']}
        bundle=lab.bundle(blueprint);owner=json.loads(bundle['task_utf8']);capture=json.loads(bundle['sources_utf8']['recording'])
        scope=('Actual local model proposals/answers; native RPC effects are counterfactual, not submitted or signed. '
               'Unprotected replay reuses guarded-trajectory proposals; not a causal comparison of two agent runs.')
        owner['authority']={'kind':'counterfactual','basis':[{'source':'basis','pointer':''}],'note':scope}
        owner['run']['id']='proposal-'+str(case['index'])+'-'+item['policy']
        owner['run']['chain_id']='proposal-projection-'+str(case['seed'])+'-'+item['policy']
        owner['run']['horizon_note']='Finite synthetic projection only, not observed consensus, balances or transaction execution.'
        owner['notes']=pack({'studyPlanSha256':sha256(plan_raw).hexdigest(),'modelCallsSha256':sha256(calls_raw).hexdigest(),
            'executionSha256':sha256(execution_raw).hexdigest(),'modelSha256':plan['artifacts']['modelSha256'],
            'referenceMode':'separate-original-Python-process-same-author','paymentScope':'counterfactual'}).decode()
        capture['chainId']=owner['run']['chain_id'];capture['utilityObservations']=item['observations']
        capture['syntheticProvenance']={'template':lab.provenance['template'],'sourceDigests':lab.provenance,
            'meaning':scope,'modelCallsSource':'model-calls','executionSource':'execution'}
        source_bytes={'recording':pack(capture),'basis':plan_raw,'model-calls':calls_raw,'execution':execution_raw}
        owner['sources']={name:sha256(raw).hexdigest() for name,raw in source_bytes.items()}
        bundle['task_utf8']=pack(owner).decode();bundle['sources_utf8']={name:raw.decode() for name,raw in source_bytes.items()}
        result=lab.app['assess_bundle'](bundle);report=result['report'];assert report['invocation']['status']=='assessed',report['invocation']
        actual=project(lab.app,report);matches=actual==item['expected']
        case_dir=out/('case-'+str(case['index']))/item['policy'];case_dir.mkdir(parents=True)
        save(case_dir/'bundle.json',bundle);save(case_dir/'report.json',result)
        save(case_dir/'comparison.json',{'actual':actual,'expected':item['expected'],'matches':matches})
        rows.append({'case':case['index'],'policy':item['policy'],'matches':matches,'gate':actual['gate'],
          'outputs':actual['utility'],'constraints':actual['constraints'],'coreReportSha256':sha256(pack(report)).hexdigest()})
    save(out/'reference.json',independent)
    summary={'complete':True,'allReferenceMatches':all(x['matches'] for x in rows),'cases':rows,'metrics':independent['metrics'],
      'evaluationCalls':independent['evaluationCalls'],'warmupCalls':independent['warmupCalls'],
      'financialComparisons':16*4,'utilityComparisons':16*2,'modelCallsActual':True,'nativeTransactions':0,
      'scope':independent['scope'],'coreSha256':lab.app['CORE_SHA256'],'sameAuthor':True,'externalBlindAudit':False}
    save(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='cases'}))
    return 0 if summary['allReferenceMatches'] else 1
if __name__=='__main__':raise SystemExit(main())
