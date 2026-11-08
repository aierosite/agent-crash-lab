from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import io,json,subprocess,tarfile
H=Path(__file__).resolve().parent;DIST='Gamero-Unified-QA-20261028';ROOT='/tmp/agent-crash-lab-banking-v015'
assert not (H/'BUILD.json').exists()
names=['worker/Cargo.toml','worker/Cargo.lock','worker/src/main.rs','sdk-source-inventory.json']
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w') as archive:
 for name in names:
  p=H/name;entry=tarfile.TarInfo(name);entry.size=p.stat().st_size;entry.mode=0o600
  with p.open('rb') as source:archive.addfile(entry,source)
stage='''from pathlib import Path
from hashlib import sha256
import json,sys,tarfile,shutil
root=Path('/tmp/agent-crash-lab-banking-v015');assert root.parent.resolve()==Path('/tmp');root.mkdir(exist_ok=False)
seen=set();names=set(json.loads(sys.argv[1]))
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as tar:
 for entry in tar:
  assert entry.isfile() and entry.name in names and entry.name not in seen
  p=root/entry.name;assert p.resolve().is_relative_to(root);p.parent.mkdir(parents=True,exist_ok=True)
  with tar.extractfile(entry) as source,p.open('xb') as target:shutil.copyfileobj(source,target)
  seen.add(entry.name)
assert seen==names
inv=json.loads((root/'sdk-source-inventory.json').read_bytes());up=Path('/tmp/agent-crash-lab-loop-v0131/upstream')
for name,meta in inv['files'].items():
 b=(up/name).read_bytes();assert len(b)==meta['bytes'] and sha256(b).hexdigest()==meta['sha256'],name
assert len(inv['files'])==407
old=Path('/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-agent-loop-sdk');assert sha256(old.read_bytes()).hexdigest()=='ffa1bb7abb8202268204fa0a6fd1405cb0d1ff0735f95b394ceeba858cdbebc5'
print(json.dumps({'canonicalFilesBeforeBuild':407,'originalHarnessUnchanged':True}))
'''
pre=subprocess.run(['wsl','-d',DIST,'-e','python3','-c',stage,json.dumps(names)],input=buffer.getvalue(),capture_output=True,check=True);(H/'build-precheck.json').write_bytes(pre.stdout)
command='''set -eu
export RUSTUP_HOME=/tmp/agent-crash-lab-sdk-v013-tools/rustup
export CARGO_HOME=/tmp/agent-crash-lab-sdk-v013-tools/cargo
export CARGO_TARGET_DIR=/tmp/agent-crash-lab-sdk-v013-tools/target
export CARGO_BUILD_JOBS=2
export RUSTUP_TOOLCHAIN=1.95.0
export RUSTUP_AUTO_INSTALL=0
export PATH="$CARGO_HOME/bin:$PATH"
cargo build --offline --locked --manifest-path /tmp/agent-crash-lab-banking-v015/worker/Cargo.toml
'''
with (H/'build.stdout.txt').open('xb') as out,(H/'build.stderr.txt').open('xb') as err:result=subprocess.run(['wsl','-d',DIST,'-e','sh','-s'],input=command.encode('utf-8'),stdout=out,stderr=err)
record={'atUtc':datetime.now(timezone.utc).isoformat(),'exitCode':result.returncode,'command':command,'workerSourceSha256':sha256((H/'worker/src/main.rs').read_bytes()).hexdigest(),'cargoLockSha256':sha256((H/'worker/Cargo.lock').read_bytes()).hexdigest(),'canonicalSdkRevision':'bacd081a0bd648d840b814dab7677e1f3330afbb','newHarness':True,'oldHarnessModified':False,'offline':True}
if result.returncode==0:
 post='''from pathlib import Path
from hashlib import sha256
import json
root=Path('/tmp/agent-crash-lab-banking-v015');inv=json.loads((root/'sdk-source-inventory.json').read_bytes());up=Path('/tmp/agent-crash-lab-loop-v0131/upstream')
for name,meta in inv['files'].items():
 b=(up/name).read_bytes();assert len(b)==meta['bytes'] and sha256(b).hexdigest()==meta['sha256']
old=Path('/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-agent-loop-sdk');assert sha256(old.read_bytes()).hexdigest()=='ffa1bb7abb8202268204fa0a6fd1405cb0d1ff0735f95b394ceeba858cdbebc5'
new=old.with_name('crash-lab-banking-sdk')
print(json.dumps({'canonicalFilesAfterBuild':407,'originalHarnessUnchanged':True,'sdkBinarySha256':sha256(new.read_bytes()).hexdigest(),'sdkBinaryBytes':new.stat().st_size,'cargoLockSha256':sha256((root/'worker/Cargo.lock').read_bytes()).hexdigest()}))
'''
 got=json.loads(subprocess.check_output(['wsl','-d',DIST,'-e','python3','-c',post]));assert got['cargoLockSha256']==record['cargoLockSha256'];record.update(got)
(H/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));raise SystemExit(result.returncode)
