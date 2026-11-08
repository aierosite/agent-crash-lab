from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import io,json,subprocess,tarfile

H=Path(__file__).resolve().parent
BASE=H.parent/'sdk-v0.13.1/release-checkout'
S=H.parent/'sdk-study-v0.13.0/upstream'
DIST='Gamero-Unified-QA-20261028'
ROOT='/tmp/agent-crash-lab-loop-v0131'
(H/'inspector').mkdir(exist_ok=True)
for name in ['token_policy.py','token_review.py']:(H/'inspector'/name).write_bytes((BASE/name).read_bytes())
source=subprocess.check_output(['git','-c','core.autocrlf=false','archive','bacd081a0bd648d840b814dab7677e1f3330afbb'],cwd=S)
subprocess.run(['wsl','-d',DIST,'-e','mkdir','-p',ROOT+'/upstream'],check=True)
subprocess.run(['wsl','-d',DIST,'-e','tar','xf','-','-C',ROOT+'/upstream'],input=source,check=True)
names=['REGISTRATION.json','agent_tools.py','grader.py','assess_episode.py','worker/Cargo.toml','worker/src/main.rs', 'inspector/token_policy.py','inspector/token_review.py', 'reference/grade_school_math/dataset.py','reference/grade_school_math/data/test.jsonl','reference/LICENSE']
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w') as tar:
 for name in names:tar.add(H/name,arcname=name)
subprocess.run(['wsl','-d',DIST,'-e','tar','xf','-','-C',ROOT],input=buffer.getvalue(),check=True)
command='''set -eu
export RUSTUP_HOME=/tmp/agent-crash-lab-sdk-v013-tools/rustup
export CARGO_HOME=/tmp/agent-crash-lab-sdk-v013-tools/cargo
export CARGO_TARGET_DIR=/tmp/agent-crash-lab-sdk-v013-tools/target
export CARGO_BUILD_JOBS=2
export PATH="$CARGO_HOME/bin:$PATH"
cargo build --offline --manifest-path /tmp/agent-crash-lab-loop-v0131/worker/Cargo.toml
'''
with (H/'worker-build.stdout.txt').open('xb') as out,(H/'worker-build.stderr.txt').open('xb') as err:
 result=subprocess.run(['wsl','-d',DIST,'-e','sh','-s'],input=command.encode(),stdout=out,stderr=err)
(H/'worker-build.json').write_text(json.dumps({'atUtc':datetime.now(timezone.utc).isoformat(),'exitCode':result.returncode,'command':command,'sourceGitArchiveSha256':sha256(source).hexdigest(),'linuxRoot':ROOT},indent=2)+'\n')
if result.returncode==0:(H/'worker/Cargo.lock').write_bytes(subprocess.check_output(['wsl','-d',DIST,'-e','cat',ROOT+'/worker/Cargo.lock']))
print(json.dumps({'buildExit':result.returncode,'linuxRoot':ROOT}))
raise SystemExit(result.returncode)
