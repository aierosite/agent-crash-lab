from pathlib import Path
from hashlib import sha256, file_digest
from datetime import datetime, timezone
import json, shutil, subprocess, tarfile

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
prior = H.parent / 'external-reference-audit-v0171'
index_raw = (prior / 'RESULT-INDEX.json').read_bytes()
assert sha256(index_raw).hexdigest() == 'd1d3fca80b27dbb7803ee980c3dbb19379576abbb71f2dfd3ff6545094f40c66'
index = json.loads(index_raw)
assert all(sha256((prior / n).read_bytes()).hexdigest() == m['sha256'] for n, m in index['files'].items())
for folder in ['upstream', 'vendor']:
    shutil.copytree(prior / folder, H / folder)
for name in ['original_loader.py', 'SOURCE-INDEX.json']:
    shutil.copyfile(prior / name, H / name)
(H / 'inspector').mkdir()
for name in ['token_policy.py', 'token_review.py']:
    shutil.copyfile(ROOT / 'product' / name, H / 'inspector' / name)
sdk_prior = H.parent / 'invoice-exposure-study-v016'
for name in ['sdk-source-inventory.json', 'BUILD.json']:
    shutil.copyfile(sdk_prior / name, H / name)
cache = ROOT / 'lab/live-model-runtime'
def digest(p):
    with p.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()
model_names = ['qwen2.5-1.5b-instruct-q4_k_m.gguf', 'qwen2.5-0.5b-instruct-q4_k_m.gguf']
models = [{'id': 'qwen-' + ('1.5b' if '1.5b' in name else '0.5b'), 'file': name,
           'bytes': (cache / name).stat().st_size, 'sha256': digest(cache / name)} for name in model_names]
assert models[0]['sha256'] == '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'
archive = cache / 'llama-b12110-bin-ubuntu-x64.tar.gz'
assert digest(archive) == '368227edcc229be5f9bed16a2223d79b5e41d0ac2e19bcf5825e82291c060e55'
with tarfile.open(archive) as bundle:
    members = [{'name': m.name, 'bytes': m.size} for m in bundle.getmembers()]
program = '''from pathlib import Path
from hashlib import file_digest
import json,os
names=['/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-banking-sdk','/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-agent-loop-sdk']
files=[]
for name in names:
 p=Path(name)
 with p.open('rb') as stream:digest=file_digest(stream,'sha256').hexdigest()
 files.append({'path':name,'bytes':p.stat().st_size,'sha256':digest})
active=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  first=(p/'cmdline').read_bytes().split(bytes([0]))[0].decode('utf-8')
  if first.startswith('/tmp/agent-crash-lab') and Path(first).name in ['llama-server','crash-lab-banking-sdk','crash-lab-agent-loop-sdk']:active.append({'pid':int(p.name),'executable':first})
 except (OSError,UnicodeError):pass
free=os.statvfs('/tmp')
print(json.dumps({'files':files,'activeKnownResearchBinaries':active,'tmpAvailableBytes':free.f_bavail*free.f_frsize}))
'''
r = subprocess.run(['wsl', '-d', 'Gamero-Unified-QA-20261028', '-e', 'python3', '-I', '-S', '-c', program], capture_output=True, timeout=30, check=True)
owned = json.loads(r.stdout)
assert owned['files'][0]['sha256'] == 'b340696521d9eda1fca93eb931bcd9ad24e3da6190b7daea8cd5fbedb86fa729'
assert owned['files'][1]['sha256'] == 'ffa1bb7abb8202268204fa0a6fd1405cb0d1ff0735f95b394ceeba858cdbebc5'
assert not owned['activeKnownResearchBinaries'] and owned['tmpAvailableBytes'] > 3_000_000_000
record = {'preparedAtUtc': datetime.now(timezone.utc).isoformat(), 'models': models,
          'runtime': {'file': archive.name, 'bytes': archive.stat().st_size, 'sha256': digest(archive),
                      'binarySha256': 'eaf9c1c664cc0ae1f4dea4b171bb91aac8409fcfea0574c9b6bcc93792ce2400',
                      'members': members},
          'ownedLinux': owned, 'priorReferenceAuditIndexSha256': sha256(index_raw).hexdigest(),
          'sourceMethod': 'Exact copies of sealed original typed runtime/reference loader and private dependency; no old study/source modified.',
          'newModelDownloads': 0, 'inferenceStarted': False, 'sdkStarted': False}
(H / 'RESOURCES.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'models': models, 'runtimeMembers': [x['name'] for x in members],
                  'tmpAvailableBytes': owned['tmpAvailableBytes'], 'activeOwnedBinaries': 0}))
