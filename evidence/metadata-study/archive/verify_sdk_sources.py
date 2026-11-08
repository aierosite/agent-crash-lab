"""Read-only hash check of shared canonical Rust sources and existing binaries."""
from pathlib import Path
import json, subprocess, sys
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from sdk_bridge import DIST, SHA
def verify():
    inventory = json.loads((H / 'sdk-source-inventory.json').read_bytes())
    code = '''from pathlib import Path
from hashlib import sha256,file_digest
import json,sys
inv=json.load(sys.stdin);root=Path('/tmp/agent-crash-lab-loop-v0131/upstream')
for name,meta in inv['files'].items():
 p=root/name;raw=p.read_bytes();assert len(raw)==meta['bytes'] and sha256(raw).hexdigest()==meta['sha256'],name
b=Path('/tmp/agent-crash-lab-sdk-v013-tools/target/debug')
found={}
for name in ['crash-lab-banking-sdk','crash-lab-agent-loop-sdk']:
 with (b/name).open('rb') as source:found[name]=file_digest(source,'sha256').hexdigest()
print(json.dumps({'canonicalFilesVerified':len(inv['files']),'binaries':found}))
'''
    response = subprocess.run(['wsl', '-d', DIST, '-e', 'python3', '-I', '-S', '-c', code],
        input=json.dumps(inventory).encode(), capture_output=True, timeout=30, check=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    value = json.loads(response.stdout)
    assert value['canonicalFilesVerified'] == 407 and value['binaries']['crash-lab-banking-sdk'] == SHA
    assert value['binaries']['crash-lab-agent-loop-sdk'] == 'ffa1bb7abb8202268204fa0a6fd1405cb0d1ff0735f95b394ceeba858cdbebc5'
    return value
if __name__ == '__main__':
    print(json.dumps(verify()))
