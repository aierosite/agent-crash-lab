"""Opt-in SDK-only replay of recorded billing method calls. No model or NEAR node."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import argparse,json,os,runpy,shutil,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/billing-study'
PIN='bacd081a0bd648d840b814dab7677e1f3330afbb'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--workspace',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--sdk-source',type=Path,help='Existing exact pinned SDK tree instead of fetching it');p.add_argument('--offline',action='store_true',help='Use only cached Cargo dependencies');p.add_argument('--target-dir',type=Path,help='Optional existing owned Cargo build cache; replay binary has a distinct name')
 a=p.parse_args()
 if not a.execute:p.error('Use tools/verify_billing_study.py for offline data replay, or explicitly pass --execute')
 if sys.platform!='linux' or not shutil.which('cargo'):p.error('SDK-only execution requires Linux and Rust1.95.0; offline recorded-data replay also supports Windows')
 if a.output.exists():p.error('Output exists; choose a new JSON output file')
 runpy.run_path(str(ROOT/'tools/verify_billing_study.py'))['verify'](ROOT)
 workspace=a.workspace.resolve() if a.workspace else Path(tempfile.mkdtemp(prefix='acl-billing-sdk-'))
 if a.workspace:workspace.mkdir(parents=True,exist_ok=False)
 env=dict(os.environ,RUSTUP_TOOLCHAIN='1.95.0',CARGO_BUILD_JOBS='2',CARGO_TARGET_DIR=str(a.target_dir.resolve() if a.target_dir else workspace/'target'),GIT_TERMINAL_PROMPT='0');commands=[];started=datetime.now(timezone.utc).isoformat()
 def call(label,args,data=None,timeout=900):
  with (workspace/(label+'.stdout.txt')).open('xb') as out,(workspace/(label+'.stderr.txt')).open('xb') as err:r=subprocess.run([str(x) for x in args],input=data,stdout=out,stderr=err,env=env,timeout=timeout)
  commands.append({'label':label,'command':[str(x) for x in args],'exitCode':r.returncode})
  if r.returncode:raise RuntimeError(label+' failed; original logs remain at '+str(workspace))
  return (workspace/(label+'.stdout.txt')).read_bytes()
 upstream=a.sdk_source.resolve() if a.sdk_source else workspace/'upstream'
 if not a.sdk_source:
  if not shutil.which('git'):p.error('Git is required to fetch the pinned official SDK source')
  call('clone',['git','clone','-c','core.autocrlf=false','--no-checkout','--filter=blob:none','https://github.com/near/near-sdk-rs.git',upstream],timeout=180)
  call('checkout',['git','-C',upstream,'checkout','--detach',PIN],timeout=180)
  if call('revision',['git','-C',upstream,'rev-parse','HEAD']).decode().strip()!=PIN:raise ValueError('Unexpected SDK revision')
 expected=json.loads((DATA/'sdk-source-inventory.json').read_bytes());assert expected['revision']==PIN and len(expected['files'])==407
 def source_check():
  for name,meta in expected['files'].items():
   path=upstream/name
   if not path.resolve().is_relative_to(upstream) or path.is_symlink():raise ValueError('Unsafe SDK source path')
   b=path.read_bytes()
   if len(b)!=meta['bytes'] or sha256(b).hexdigest()!=meta['sha256']:raise ValueError('Canonical SDK source differs: '+name)
 source_check();harness=workspace/'harness';shutil.copytree(DATA/'worker',harness)
 source_before={n:sha256((harness/n).read_bytes()).hexdigest() for n in ['src/main.rs','Cargo.toml','Cargo.lock']}
 manifest=(harness/'Cargo.toml').read_text(encoding='utf-8')
 for crate in ['near-contract-standards','near-sdk']:
  before='"/tmp/agent-crash-lab-loop-v0131/upstream/'+crate+'"'
  if manifest.count(before)!=1:raise ValueError('Recorded Cargo path declaration changed')
  manifest=manifest.replace(before,json.dumps(str(upstream/crate)))
 if manifest.count('name = "crash-lab-banking-sdk"')!=1:raise ValueError('Recorded package name changed')
 manifest=manifest.replace('name = "crash-lab-banking-sdk"','name = "crash-lab-billing-replay"');(harness/'Cargo.toml').write_text(manifest,encoding='utf-8')
 lock=(harness/'Cargo.lock').read_text(encoding='utf-8')
 if lock.count('name = "crash-lab-banking-sdk"')!=1:raise ValueError('Recorded root lock package changed')
 (harness/'Cargo.lock').write_text(lock.replace('name = "crash-lab-banking-sdk"','name = "crash-lab-billing-replay"'),encoding='utf-8')
 compiler=call('compiler',['rustc','--version','--verbose']).decode().strip();args=['cargo','build','--locked','--manifest-path',harness/'Cargo.toml']
 if a.offline:args.insert(2,'--offline')
 call('build',args);wire=json.loads((DATA/'actual/sdk-wire.json').read_bytes());input_raw=b''.join(row['requestUtf8'].encode('utf-8') for row in wire)
 binary=Path(env['CARGO_TARGET_DIR'])/'debug/crash-lab-billing-replay';actual=call('sdk-replay',[binary],input_raw,timeout=60);original=b''.join(row['responseUtf8'].encode('utf-8') for row in wire)
 if actual!=original:raise ValueError('Fresh SDK response bytes differ from recorded30-message stream')
 if len(actual.splitlines())!=len(wire):raise ValueError('SDK response count differs')
 source_check()
 if sha256((harness/'src/main.rs').read_bytes()).hexdigest()!=source_before['src/main.rs']:raise ValueError('Recorded Rust method harness source changed')
 record={'format':'agent-crash-lab/billing-sdk-replay-v1','startedAtUtc':started,'endedAtUtc':datetime.now(timezone.utc).isoformat(),'sdkRevision':PIN,'canonicalSourceFilesChecked':407,'compiler':compiler,'sdkCommandsExecuted':len(wire),'sdkPaymentMethodsExecuted':sum(json.loads(r['requestUtf8'])['op']=='pay' for r in wire),'fullSdkResponseBytesMatched':True,'sdkResponseSha256':sha256(actual).hexdigest(),'binarySha256':sha256(binary.read_bytes()).hexdigest(),'originalRustHarnessSourceSha256':source_before['src/main.rs'],'portableBuildAdaptations':['Only dependency path strings point to the selected canonical tree.','Only the OWN root package name changes to crash-lab-billing-replay in Cargo.toml/Cargo.lock, preventing overwrite of the original recorded banking worker.','Original Rust source and every upstream SDK source file remain byte-identical.'],'newModelCalls':0,'newTransactions':0,'newChainRpc':0,'existingSdkTreeUsed':bool(a.sdk_source),'cargoOffline':a.offline,'sharedBuildCacheUsed':bool(a.target_dir),'workspace':str(workspace),'commands':commands,'meaning':'Actual official SDK mock-host methods freshly reexecuted for recorded model-selected arguments; exact full stdout response stream matches. This reruns neither the model nor HTTP merchant, deploys no WASM and authenticates no consensus. Not independent blind evaluation.'}
 a.output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record))
if __name__=='__main__':main()
