"""Stage only cached local files, run the locked actor and collect every outcome."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,tarfile,sys,zipfile

H=Path(__file__).resolve().parent
CACHE=H.parent.parent/'lab/live-model-runtime'
DIST='Gamero-Unified-QA-20261028'
ROOT='/tmp/agent-crash-lab-loop-v0131'
lock=json.loads((H/'LOCK.json').read_bytes())
sources={name:H/name for name in ['REGISTRATION.json','LOCK.json',*lock['sources']]}
sources.update({'runtime.tar.gz':CACHE/'llama-b12110-bin-ubuntu-x64.tar.gz','model.gguf':CACHE/'qwen2.5-1.5b-instruct-q4_k_m.gguf'})
sizes={n:p.stat().st_size for n,p in sources.items()}
program='''from pathlib import Path
import json,sys,tarfile,shutil
root=Path(sys.argv[1]);sizes=json.loads(sys.argv[2]);seen=set()
assert root==Path('/tmp/agent-crash-lab-loop-v0131') and root.is_dir()
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as tar:
 for member in tar:
  assert member.isfile() and member.name in sizes and member.name not in seen and member.size==sizes[member.name]
  path=root/member.name;assert path.resolve().is_relative_to(root)
  path.parent.mkdir(parents=True,exist_ok=True)
  with tar.extractfile(member) as src,path.open('wb') as out:shutil.copyfileobj(src,out,1024*1024)
  seen.add(member.name)
assert seen==set(sizes)
print(json.dumps({'stagedFiles':len(seen)}))
'''
print(json.dumps({'phase':'stage-cached-files','bytes':sum(sizes.values()),'externalModelRequests':0}),flush=True)
stage=subprocess.Popen(['wsl','-d',DIST,'-e','python3','-c',program,ROOT,json.dumps(sizes)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
with tarfile.open(fileobj=stage.stdin,mode='w|') as tar:
 for name,path in sources.items():
  info=tarfile.TarInfo(name);info.size=sizes[name];info.mode=0o600
  with path.open('rb') as stream:tar.addfile(info,stream)
stage.stdin.close();stdout=stage.stdout.read();stderr=stage.stderr.read();assert stage.wait()==0,stderr.decode(errors='replace')
print(stdout.decode().strip(),flush=True)
command=['wsl','-d',DIST,'-e','python3','-I','-S',ROOT+'/actor.py','--model',ROOT+'/model.gguf','--runtime',ROOT+'/runtime.tar.gz','--sdk','/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-agent-loop-sdk','--out',ROOT+'/actual']
process=subprocess.Popen(command,stdout=sys.stdout,stderr=sys.stderr,creationflags=subprocess.CREATE_NO_WINDOW)
(H/'transport-state.json').write_text(json.dumps({'startedAtUtc':datetime.now(timezone.utc).isoformat(),'ownedWindowsTransportPid':process.pid,'linuxRoot':ROOT,'phase':'locked-real-model-loop'},indent=2)+'\n')
code=process.wait()
collect='''from pathlib import Path
import zipfile,sys
root=Path(sys.argv[1]);out=root/'actual'
allowed={'run.json','calls.json','episodes.json','sdk-wire.json','execution.json','server.json','runtime.log','sdk.log'}
with zipfile.ZipFile(sys.stdout.buffer,'w',zipfile.ZIP_DEFLATED) as z:
 for p in out.iterdir():
  if p.is_file():
   assert p.name in allowed and not p.is_symlink() and p.stat().st_size<64*1024**2,p.name
   z.write(p,p.name)
'''
with (H/'actual-artifacts.zip').open('xb') as out:subprocess.run(['wsl','-d',DIST,'-e','python3','-c',collect,ROOT],stdout=out,check=True)
target=H/'actual';target.mkdir(exist_ok=False)
with zipfile.ZipFile(H/'actual-artifacts.zip') as z:
 for name in z.namelist():
  assert Path(name).name==name
  (target/name).write_bytes(z.read(name))
print(json.dumps({'phase':'collected','actorExitCode':code,'folder':str(target)}),flush=True)
raise SystemExit(code)
