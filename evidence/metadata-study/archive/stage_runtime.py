"""Stage only previously cached bytes and own helpers in a new owned WSL root."""
from pathlib import Path
from hashlib import file_digest
import json, subprocess, sys, tarfile
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from sdk_bridge import DIST
from protocol import pack, utc
resources = json.loads((H / 'RESOURCES.json').read_bytes())
cache = H.parent.parent / 'lab/live-model-runtime'
scripts = ['model_http.py', 'model_supervisor.py', 'RESOURCES.json']
files = [(cache / r['file'], r['file'], r['sha256']) for r in resources['models'] + [resources['runtime']]]
for name in scripts:
    with (H / name).open('rb') as stream:
        files.append((H / name, name, file_digest(stream, 'sha256').hexdigest()))
for path, name, expected in files:
    with path.open('rb') as stream:
        assert file_digest(stream, 'sha256').hexdigest() == expected, name
manifest = {name: digest for _, name, digest in files}
code = '''from pathlib import Path
from hashlib import file_digest
import json,sys,tarfile
h=Path('/tmp/agent-crash-lab-multitask-v0171')
assert h.parent.resolve()==Path('/tmp') and not h.exists()
h.mkdir()
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as stream:
 for member in stream:
  assert member.isfile() and '/' not in member.name and not member.name.startswith('.')
  stream.extract(member,h,filter='data')
manifest=json.loads(sys.argv[1])
for name,expected in manifest.items():
 with (h/name).open('rb') as source: assert file_digest(source,'sha256').hexdigest()==expected,name
(h/'STAGING-MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
target=h/'runtime';target.mkdir()
with tarfile.open(h/'llama-b12110-bin-ubuntu-x64.tar.gz') as archive:
 members=archive.getmembers();assert len(members)<200 and sum(max(0,x.size) for x in members)<256*1024**2
 archive.extractall(target,filter='data')
print(json.dumps({'root':str(h),'files':len(manifest),'verified':True,'modelRequests':0}),flush=True)
'''
proc = subprocess.Popen(['wsl', '-d', DIST, '-e', 'python3', '-I', '-S', '-c', code, json.dumps(manifest)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW)
with tarfile.open(fileobj=proc.stdin, mode='w|') as stream:
    for path, name, _ in files:
        stream.add(path, arcname=name, recursive=False)
proc.stdin.close()
proc.stdin = None
reply, error = proc.communicate(timeout=120)
report = {'atUtc': utc(), 'returncode': proc.returncode, 'stdout': reply.decode('utf-8'),
          'stderr': error.decode('utf-8'), 'manifest': manifest, 'modelRequests': 0}
(H / 'STAGING.json').write_bytes(pack(report) + b'\n')
print(json.dumps(report))
assert proc.returncode == 0
