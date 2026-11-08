"""Replay recorded model proposals and synthetic payment projections. No inference or network."""
from pathlib import Path, PurePosixPath
from hashlib import sha256
import argparse, json, runpy, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence/proposal-study'
INDEX_SHA256='e614e58499a94232ada90b53c43528f2a5e162cdf2ffd05af666c16d6c6045c5'
PLAN_SHA256='341dcba29ee869b46c7987d4dfce665b734a38162b95a1f99fb9a3e6b6e1ab2e'

def need(value,message):
    if not value:raise ValueError(message)

def canonical(value):
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()

def decode(raw):
    def unique(pairs):
        result=dict(pairs);need(len(result)==len(pairs),'Duplicate evidence JSON member');return result
    def constant(_):raise ValueError('Non-finite evidence JSON number')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=constant)

def checked_index(directory):
    directory=directory.resolve();raw=(directory/'study-index.json').read_bytes()
    need(sha256(raw).hexdigest()==INDEX_SHA256,'Study index differs from the reviewed release')
    index=decode(raw)
    need(index['format']=='agent-crash-lab/proposal-study-index-v1','Unsupported study index')
    for name,expected in index['files'].items():
        parts=PurePosixPath(name)
        need(not parts.is_absolute() and '\\' not in name and ':' not in name
             and all(p not in ('.','..') for p in parts.parts),'Unsafe study path')
        path=directory/name
        need(path.resolve()==path and path.is_file(),'Missing or redirected study file: '+name)
        data=path.read_bytes()
        need({'bytes':len(data),'sha256':sha256(data).hexdigest()}==expected,'Study evidence changed: '+name)
    plan_raw=(directory/'locked-plan.json').read_bytes();plan=decode(plan_raw)
    need(sha256(plan_raw).hexdigest()==PLAN_SHA256==index['planSha256'],'Study plan differs from registration')
    need(sha256((directory/'DESIGN.json').read_bytes()).hexdigest()==plan['designSha256'],'Study design changed')
    need(sha256((directory/'base-release-manifest.json').read_bytes()).hexdigest()==plan['baseManifestSha256'],
         'Recorded baseline manifest changed')
    for name,digest in plan['sources'].items():
        need(sha256((directory/name).read_bytes()).hexdigest()==digest,'Locked study source changed: '+name)
    need([(r['case'],r['policy']) for r in index['cases']]==
         [(i,p) for i in range(8) for p in ('unprotected','guarded')],'Study selection is incomplete')
    return index

def verify(directory=EVIDENCE):
    directory=directory.resolve();index=checked_index(directory)
    # Only the reviewed, byte-pinned oracle is executed. The archived inference harness is never run.
    process=subprocess.run([sys.executable,'-I','-S',str(directory/'proposal_oracle.py'),
                            str(directory/'locked-plan.json'),str(directory/'actual')],
                           capture_output=True,timeout=15)
    need(process.returncode==0,'Recorded trajectory was rejected by the separate reference: '+
         process.stdout.decode(errors='replace')[-500:])
    reference=decode(process.stdout)
    need(len(reference['cases'])==16,'Reference returned an incomplete study')
    app=runpy.run_path(str(ROOT/'workbench.py'))
    need(app['CORE_SHA256']==index['coreSha256'],'Assessor source differs from the registered replay baseline')
    rows=[]
    common={'basis':(directory/'locked-plan.json').read_bytes(),
            'model-calls':(directory/'actual/calls.json').read_bytes(),
            'execution':(directory/'actual/execution.json').read_bytes()}
    for entry,expected in zip(index['cases'],reference['cases']):
        need((entry['case'],entry['policy'])==(expected['case'],expected['policy']),'Reference case order changed')
        sources={**common,'recording':(directory/entry['recording']).read_bytes()}
        task=(directory/entry['task']).read_bytes();owner=decode(task)
        need(owner['authority']['kind']=='counterfactual','Synthetic payments were relabeled as observed')
        report=app['evaluate'](task,sources)['report']
        actual={'constraints':{c['id']:{'exact_total':c.get('exact_total'),'status':c['status']} for c in report['constraints']},
                'utility':{u['id']:u['status'] for u in report['utility']['required']},
                'financial_scope_complete':report['coverage']['financial_scope_complete'],'gate':app['gate'](report)}
        need(report['invocation']['status']=='assessed' and actual==expected['expected'],
             'Assessment differs from the separate reference: '+entry['name'])
        digest=sha256(canonical(report)).hexdigest()
        need(digest==entry['coreReportSha256'],'Full replay report changed: '+entry['name'])
        rows.append({'case':entry['case'],'policy':entry['policy'],'gate':actual['gate'],
                     'outputs':actual['utility'],'fullReportSha256':digest,'referenceMatched':True})
    return {'verified':True,'meaning':'Assessor and evidence replay agree; this is not a successful-agent score.',
            'model':decode((directory/'locked-plan.json').read_bytes())['artifacts'],
            'metrics':reference['metrics'],'evaluationCallsRecorded':reference['evaluationCalls'],
            'warmupCallsRecorded':reference['warmupCalls'],'trajectories':8,'correlatedProjections':16,
            'financialComparisons':64,'utilityComparisons':32,'cases':rows,
            'newInferenceCalls':0,'nativeTransactions':0,'paymentScope':'counterfactual',
            'referenceMode':'separate-original-Python-process-same-author','externalBlindAudit':False,
            'scope':reference['scope'],'coreSha256':app['CORE_SHA256'],'planSha256':PLAN_SHA256}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,help='Write replay results to a new JSON file')
    args=parser.parse_args()
    try:
        result=verify()
        if args.out:
            with args.out.open('xb') as stream:stream.write(canonical(result)+b'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('cases','model')}));return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as error:
        print(json.dumps({'verified':False,'error':str(error)}));return 2

if __name__=='__main__':raise SystemExit(main())
