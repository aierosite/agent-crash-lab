"""Reproduce the registered synthetic partial-evidence failure and its correction offline."""
from pathlib import Path, PurePosixPath
from hashlib import sha256
from copy import deepcopy
import argparse,json,re,runpy,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence/async-study'
INDEX_SHA256='3179087da0082cc0e6f302ecaa0ff88fa26055175d87df35e3f74a3289be17fc'
REGISTRATION_SHA256='71f07963746f8e468f479a835b0001a3d791f42acbba2f9b7a91d840dace2553'

def need(value,message):
    if not value:raise ValueError(message)

def canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def digest(value):return sha256(canonical(value)).hexdigest()
def decode(raw):
    def unique(pairs):
        result=dict(pairs);need(len(result)==len(pairs),'Duplicate study JSON member');return result
    return json.loads(raw,object_pairs_hook=unique)

def checked_registration(directory=EVIDENCE):
    directory=directory.resolve();raw=(directory/'index.json').read_bytes()
    need(sha256(raw).hexdigest()==INDEX_SHA256,'Async study index changed')
    index=decode(raw)
    need(index['format']=='agent-crash-lab/async-index-v1','Unsupported async index')
    for name,expected in index['files'].items():
        parts=PurePosixPath(name);path=directory/name
        need(not parts.is_absolute() and '\\' not in name and ':' not in name and '..' not in parts.parts
             and path.resolve()==path and path.is_file(),'Missing or redirected async evidence: '+name)
        data=path.read_bytes()
        need({'bytes':len(data),'sha256':sha256(data).hexdigest()}==expected,'Async study evidence changed: '+name)
    raw=(directory/'registration.json').read_bytes();registration=decode(raw)
    need(sha256(raw).hexdigest()==REGISTRATION_SHA256==index['registrationSha256'],'Async registration changed')
    for name,expected in registration['sources'].items():
        need(sha256((directory/'sources'/name).read_bytes()).hexdigest()==expected,'Registered source changed')
    need(sha256((directory/'baseline/agent_crash_lab.py').read_bytes()).hexdigest()==registration['baseCoreSha256'],
         'Frozen original assessor changed')
    return registration

def constructors():return runpy.run_path(str(ROOT/'tools/async_lab.py'))

def projection(report):
    return {r['id']:{key:r.get(key) for key in ['known_subtotal','exact_total','status']} for r in report.get('constraints',[])}

def assess(module,bundle):
    return module['assess'](bundle['task_utf8'].encode(),{k:v.encode() for k,v in bundle['sources_utf8'].items()})

def verify(directory=EVIDENCE):
    directory=directory.resolve();registration=checked_registration(directory);builder=constructors()
    app=runpy.run_path(str(ROOT/'workbench.py'));old={'__name__':'registered_original_assessor'}
    old_source=(directory/'baseline/agent_crash_lab.py').read_bytes()
    exec(compile(old_source,'registered-original-assessor','exec'),old)
    current={'assess':app['core'].assess}
    prior={row['name']:row for row in decode((directory/'original-results.json').read_bytes())['cases']}
    fixed={row['name']:row for row in decode((directory/'initial-candidate-results.json').read_bytes())['cases']}
    rows=[];old_matches=0;current_matches=0;generated=[]
    with tempfile.TemporaryDirectory(prefix='Crash Lab async reference ') as temporary:
        for plan in registration['plans']:
            need(re.fullmatch('[A-Za-z0-9-]{1,128}',plan['id']) is not None,'Invalid registered plan identity')
            path=Path(temporary)/(plan['id']+'.json');path.write_bytes(canonical(plan)+b'\n')
            result=subprocess.run([sys.executable,'-I','-S',str(directory/'sources/async_reference.py'),str(path)],
                                  capture_output=True,timeout=10)
            need(result.returncode==0,'Separate async reference rejected a registered plan')
            expected=decode(result.stdout)
            for variant in ['original','reversed','duplicated']:
                name=plan['id']+'-'+variant;bundle=builder['bundle'](plan,variant)
                need(sha256(canonical(bundle)+b'\n').hexdigest()==registration['bundles']['bundles/'+name+'.json'],
                     'Portable builder differs from registered input: '+name)
                original=assess(old,bundle);report=assess(current,bundle)
                need(original['invocation']['status']==report['invocation']['status']=='assessed','Assessment rejected: '+name)
                actual=projection(report);old_actual=projection(original)
                need(digest(original)==prior[name]['fullReportSha256'] and old_actual==prior[name]['actual'],
                     'Original failure did not reproduce exactly: '+name)
                need(actual==expected and [u['status'] for u in report['utility']['required']]==['passed','passed'],
                     'Current result differs from the separate reference: '+name)
                need(digest(report)==fixed[name]['fullReportSha256'],'Current report differs from validated candidate: '+name)
                old_matches+=old_actual==expected;current_matches+=actual==expected
                generated.append(name)
                rows.append({'name':name,'plan':plan['id'],'variant':variant,'financial':actual,
                    'originalMatched':old_actual==expected,'currentMatched':True,'gate':app['gate'](report),
                    'originalFullReportSha256':digest(original),'currentFullReportSha256':digest(report)})
    need(len(rows)==96 and set(generated)==set(prior)==set(fixed),'Incomplete registered selection')
    compatibility=[]
    for item in decode((directory/'initial-candidate-audit.json').read_bytes())['previousBaselines']:
        row=app['BASELINES'][item['name']]
        report=app['core'].assess((ROOT/row['task']).read_bytes(),{key:(ROOT/name).read_bytes() for key,name in row['sources'].items()})
        normalized=deepcopy(report);normalized['invocation']['version']='0.1.1'
        need(digest(normalized)==item['originalFullReportSha256'] and digest(report)==item['candidateFullReportSha256'],
             'Previous baseline changed beyond declared version: '+item['name'])
        compatibility.append(item['name'])
    return {'verified':True,'meaning':'Same-author synthetic replay and failure reproduction, not external accuracy.',
            'registrationSha256':REGISTRATION_SHA256,'plans':32,'correlatedBundles':96,
            'original':{'matched':old_matches,'disagreed':96-old_matches,'coreSha256':registration['baseCoreSha256']},
            'current':{'matched':current_matches,'disagreed':96-current_matches,'coreSha256':app['CORE_SHA256'],
                       'coreVersion':app['core'].VERSION},'previousBaselinesUnchangedExceptVersion':compatibility,'cases':rows,
            'referenceMode':'separate-original-Python-process-same-author','externalBlindAudit':False,
            'modelCalls':0,'nativeTransactions':0,'scope':registration['scope']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path);args=parser.parse_args()
    try:
        result=verify()
        if args.out:
            with args.out.open('xb') as stream:stream.write(canonical(result)+b'\n')
        print(json.dumps({key:value for key,value in result.items() if key not in ['cases','previousBaselinesUnchangedExceptVersion']}));return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as error:
        print(json.dumps({'verified':False,'error':str(error)}));return 2

if __name__=='__main__':raise SystemExit(main())
