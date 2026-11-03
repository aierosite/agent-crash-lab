"""Windows convenience transport for the optional owned native runner. No secrets on stdout."""
from pathlib import Path
import argparse,base64,hashlib,io,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--distro',required=True);parser.add_argument('--binary',required=True);a=parser.parse_args()
    # Arguments are passed through JSON stdin, never shell interpolation.
    program=r'''
from pathlib import Path
import base64,io,json,subprocess,sys,tempfile,zipfile
c=json.load(sys.stdin);root=Path(tempfile.mkdtemp(prefix='acl-native-product-'));script=root/'native_crash.py';script.write_bytes(base64.b64decode(c['source']))
r=subprocess.run([sys.executable,str(script),'--binary',c['binary'],'--output',str(root/'output')],capture_output=True,timeout=160)
if r.returncode:print(json.dumps({'exitCode':r.returncode,'error':r.stderr.decode(errors='replace')[-6000:]}));raise SystemExit(1)
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p in (root/'output').glob('*.json'):z.write(p,p.name)
print(json.dumps({'exitCode':0,'summary':json.loads(r.stdout),'archive':base64.b64encode(b.getvalue()).decode()}))
'''
    source=(ROOT/'tools/native_crash.py').read_bytes()
    config={'source':base64.b64encode(source).decode(),'binary':a.binary}
    r=subprocess.run(['wsl.exe','-d',a.distro,'--','python3','-c',program],input=json.dumps(config).encode(),capture_output=True,timeout=175)
    result=json.loads(r.stdout)
    if r.returncode:print(json.dumps(result));raise SystemExit(1)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result['archive']))) as z:
        for name in ['native-precommit.json','native-observation.json']:(ROOT/'evidence'/name).write_bytes(z.read(name))
    print(json.dumps({'exitCode':0,'summary':result['summary'],'runnerSha256':hashlib.sha256(source).hexdigest(),'importedInto':'evidence/'}))
if __name__=='__main__':main()
