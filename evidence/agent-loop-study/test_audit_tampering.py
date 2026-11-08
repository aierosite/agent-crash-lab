from pathlib import Path
from hashlib import sha256
import json,shutil,subprocess,sys,tempfile

H=Path(__file__).resolve().parent
def save(path,value):path.write_text(json.dumps(value)+'\n',encoding='utf-8')
def change_answer(root):
 p=root/'actual/episodes.json';x=json.loads(p.read_bytes());x[0]['answers']['A']='#### 123456789';save(p,x)
def change_sdk(root):
 p=root/'actual/episodes.json';x=json.loads(p.read_bytes());x[0]['sdkRows'][0]['amount']='99';save(p,x)
def orphan_sdk(root):
 p=root/'actual/sdk-wire.json';x=json.loads(p.read_bytes());x.append(next(y for y in x if json.loads(y['requestUtf8'])['op']=='pay'));save(p,x)
def change_source_and_relock(root):
 source=root/'grader.py';source.write_bytes(source.read_bytes()+b'\n# changed after observation\n');p=root/'LOCK.json';x=json.loads(p.read_bytes());x['sources']['grader.py']={'bytes':source.stat().st_size,'sha256':sha256(source.read_bytes()).hexdigest()};save(p,x)
def reseal_question(root):
 p=root/'actual/episodes.json';episodes=json.loads(p.read_bytes())
 for e in episodes:
  for s in e['steps']:
   if 'responseUtf8' in s and 'packet' in (body:=json.loads(s['responseUtf8'])):
    body['packet']['question']+=' altered';text=json.dumps(body,sort_keys=True,separators=(',',':'))+'\n';s['responseUtf8']=text;s['responseSha256']=sha256(text.encode()).hexdigest()
    event=next(v for v in e['hostEvents'] if v['callId']==str(s['modelCallId']));event['responseUtf8']=text;save(p,episodes);return
 raise AssertionError('No delivered packet')

results=[]
for label,mutate in [('baseline',None),('edited-final-answer',change_answer),('edited-sdk-effect',change_sdk),('orphan-sdk-pay',orphan_sdk),('source-relocked-after-model',change_source_and_relock),('question-resealed-in-http-traces',reseal_question)]:
 with tempfile.TemporaryDirectory(prefix='crash-lab-agent-audit-') as tmp:
  root=Path(tmp);names=[*json.loads((H/'LOCK.json').read_bytes())['sources'],'REGISTRATION.json','LOCK.json','audit_actual.py']
  for n in names:
   dest=root/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(H/n,dest)
  shutil.copytree(H/'actual',root/'actual')
  if mutate:mutate(root)
  run=subprocess.run([sys.executable,'-I','-S',str(root/'audit_actual.py')],capture_output=True,timeout=30)
  okay=run.returncode==0 if mutate is None else run.returncode!=0
  results.append({'id':label,'exitCode':run.returncode,'expectedAccepted':mutate is None,'matched':okay})
  assert okay,(label,run.stdout[-1000:],run.stderr[-1000:])
(H/'AUDIT-TAMPERING.json').write_text(json.dumps({'checks':results,'meaning':'Same-author actual-data integrity controls, not an independent accuracy estimate.'},indent=2)+'\n')
print(json.dumps(results))
