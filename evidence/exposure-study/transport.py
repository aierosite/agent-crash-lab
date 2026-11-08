"""Stage controls then locked actual-model run in the existing owned billing build root."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,subprocess,sys,tarfile,zipfile
H=Path(__file__).resolve().parent;ROOT='/tmp/agent-crash-lab-invoice-exposure-v016';DIST='Gamero-Unified-QA-20261028';CACHE=H.parent.parent/'lab/live-model-runtime';phase=sys.argv[1];assert phase in ['controls','run']
sources={str(p.relative_to(H)).replace('\\','/'):p for p in H.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'actual' not in p.parts and p.suffix not in ['.zip','.log'] and p.name!='transport-state.json'}
if phase=='run':assert (H/'LOCK.json').exists();sources.update({'model.gguf':CACHE/'qwen2.5-1.5b-instruct-q4_k_m.gguf','runtime.tar.gz':CACHE/'llama-b12110-bin-ubuntu-x64.tar.gz'})
sizes={n:p.stat().st_size for n,p in sources.items()}
program='''from pathlib import Path
from hashlib import sha256
import sys,tarfile,json,shutil
root=Path('/tmp/agent-crash-lab-invoice-exposure-v016');assert root.parent.resolve()==Path('/tmp');root.mkdir(exist_ok=True);assert root.resolve()==root and not (root/'LOCK.json').exists() and not (root/'actual').exists()
sizes=json.loads(sys.argv[1]);seen=set()
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as tar:
 for member in tar:
  assert member.isfile() and member.name in sizes and member.name not in seen and member.size==sizes[member.name]
  p=root/member.name;assert p.resolve().is_relative_to(root);p.parent.mkdir(parents=True,exist_ok=True)
  if member.name.startswith('worker/') and p.exists():
   b=tar.extractfile(member).read();assert p.read_bytes()==b,'Built worker source changed';seen.add(member.name);continue
  with tar.extractfile(member) as source,p.open('wb') as target:shutil.copyfileobj(source,target,1024*1024)
  seen.add(member.name)
assert seen==set(sizes)
inv=json.loads((root/'sdk-source-inventory.json').read_bytes());up=Path('/tmp/agent-crash-lab-loop-v0131/upstream')
for name,meta in inv['files'].items():
 b=(up/name).read_bytes();assert len(b)==meta['bytes'] and sha256(b).hexdigest()==meta['sha256']
assert len(inv['files'])==407
build=json.loads((root/'BUILD.json').read_bytes());binary=Path('/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-banking-sdk');assert sha256(binary.read_bytes()).hexdigest()==build['sdkBinarySha256']
assert sha256(binary.with_name('crash-lab-agent-loop-sdk').read_bytes()).hexdigest()=='ffa1bb7abb8202268204fa0a6fd1405cb0d1ff0735f95b394ceeba858cdbebc5'
print(json.dumps({'stagedFiles':len(seen),'canonicalSdkFiles':407,'newSdkBinarySha256':build['sdkBinarySha256'],'oldHarnessUnchanged':True}))
'''
print(json.dumps({'phase':'stage-'+phase,'bytes':sum(sizes.values()),'newModelDownloads':0}),flush=True)
process=subprocess.Popen(['wsl','-d',DIST,'-e','python3','-c',program,json.dumps(sizes)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
with tarfile.open(fileobj=process.stdin,mode='w|') as tar:
 for name,p in sources.items():
  entry=tarfile.TarInfo(name);entry.size=sizes[name];entry.mode=0o600
  with p.open('rb') as stream:tar.addfile(entry,stream)
process.stdin.close();stdout=process.stdout.read();stderr=process.stderr.read();assert process.wait()==0,stderr.decode(errors='replace');(H/('controls-precheck.json' if phase=='controls' else 'run-precheck.json')).write_bytes(stdout);print(stdout.decode().strip(),flush=True)
if phase=='controls':
 process=subprocess.run(['wsl','-d',DIST,'-e','python3','-S',ROOT+'/controls.py','/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-banking-sdk'],capture_output=True)
 (H/'controls.stdout.txt').write_bytes(process.stdout);(H/'controls.stderr.txt').write_bytes(process.stderr);print(process.stderr.decode(errors='replace'),end='');code=process.returncode
 collect='''from pathlib import Path
import sys,zipfile
root=Path('/tmp/agent-crash-lab-invoice-exposure-v016')
with zipfile.ZipFile(sys.stdout.buffer,'w',zipfile.ZIP_DEFLATED) as z:
 for name in ['CONTROLS.json','controls-sdk.log']:
  p=root/name
  if p.exists():z.write(p,name)
''';dest=H/'controls-artifacts.zip';target=H
else:
 process=subprocess.Popen(['wsl','-d',DIST,'-e','python3','-I','-S',ROOT+'/actor.py'],stdout=sys.stdout,stderr=sys.stderr,creationflags=subprocess.CREATE_NO_WINDOW);(H/'transport-state.json').write_text(json.dumps({'startedAtUtc':datetime.now(timezone.utc).isoformat(),'ownedWindowsTransportPid':process.pid,'linuxRoot':ROOT},indent=2)+'\n',encoding='utf-8');code=process.wait()
 collect='''from pathlib import Path
import sys,zipfile
out=Path('/tmp/agent-crash-lab-invoice-exposure-v016/actual')
with zipfile.ZipFile(sys.stdout.buffer,'w',zipfile.ZIP_DEFLATED) as z:
 for p in out.iterdir():
  if p.is_file():
   assert not p.is_symlink() and p.stat().st_size<32*1024**2;z.write(p,p.name)
''';dest=H/'actual-artifacts.zip';target=H/'actual';target.mkdir(exist_ok=False)
with dest.open('xb') as stream:subprocess.run(['wsl','-d',DIST,'-e','python3','-c',collect],stdout=stream,check=True)
with zipfile.ZipFile(dest) as z:
 for name in z.namelist():assert Path(name).name==name;(target/name).write_bytes(z.read(name))
if phase=='controls' and code==0:
 controls=json.loads((H/'CONTROLS.json').read_bytes());assert controls['executedTests']==11 and controls['failures']==controls['errors']==controls['skipped']==0
 files={str(p.relative_to(H)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha256(p.read_bytes()).hexdigest()} for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.zip' and p.name not in ['LOCK.json','transport-state.json']}
 (H/'LOCK.json').write_text(json.dumps({'lockedAtUtc':datetime.now(timezone.utc).isoformat(),'registrationSha256':sha256((H/'REGISTRATION.json').read_bytes()).hexdigest(),'sources':files},indent=2)+'\n',encoding='utf-8');print(json.dumps({'phase':'controls-pass-and-source-locked','files':len(files),'inferenceCalls':0}))
elif phase=='run':print(json.dumps({'phase':'collected','actorExitCode':code}))
raise SystemExit(code)
