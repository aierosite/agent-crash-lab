"""Bounded owned-process token policy measurements; no network/model/contract execution."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import argparse,copy,json,platform,runpy,statistics,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
CASES=['corpus','repeated-final-128','evidence-over-bound']

def child(case):
 peak=runpy.run_path(str(ROOT/'tools/measure_resources.py'))['peak_working_set'];before=peak();start=time.perf_counter();api=runpy.run_path(str(ROOT/'token_policy.py'));import_ms=(time.perf_counter()-start)*1000;pack=api['pack'];reference=json.loads((ROOT/'verification/token-policy/reference.json').read_bytes());c=next(c for c in reference['cases'] if c['id']=='used-all');task=(ROOT/c['task']).read_bytes();evidence=(ROOT/c['evidence']).read_bytes();inputs=[]
 if case=='corpus':
  inputs=[(c['id'],(ROOT/c['task']).read_bytes(),(ROOT/c['evidence']).read_bytes()) for c in reference['cases']]
  enc=ROOT/'verification/token-policy/encoding-controls'
  for c in json.loads((enc/'reference.json').read_bytes())['cases']:inputs.append((c['id'],(enc/c['id']/'task.json').read_bytes(),(enc/c['id']/'evidence.json').read_bytes()))
 elif case=='repeated-final-128':
  e=json.loads(evidence);e['observations']=[copy.deepcopy(e['observations'][0]) for _ in range(128)];evidence=pack(e);t=json.loads(task);t['evidence_sha256']=sha256(evidence).hexdigest();inputs=[(case,pack(t),evidence)]
 else:inputs=[(case,task,b' '*(2*1024*1024+1))]
 def inspect(t,e):
  try:return api['assess'](t,e)
  except ValueError as ex:return {'error':str(ex)}
 rows=[];samples=[]
 for cid,t,e in inputs:
  warm=inspect(t,e);digest=sha256(pack(warm)).hexdigest();times=[]
  if case=='repeated-final-128':assert warm['gate']==0 and warm['intents'][0]['gross_known']=='100' and warm['graphs'][0]['final_observations']==128
  if case=='evidence-over-bound':assert 'error' in warm
  for _ in range(3):
   start=time.perf_counter();result=inspect(t,e);elapsed=(time.perf_counter()-start)*1000;assert sha256(pack(result)).hexdigest()==digest and elapsed<30000;times.append(round(elapsed,3));samples.append(elapsed)
  rows.append({'id':cid,'inputBytes':len(t)+len(e),'taskSha256':sha256(t).hexdigest(),'evidenceSha256':sha256(e).hexdigest(),'reportSha256':digest,'repeatedMs':times})
 return {'case':case,'samples':len(samples),'assessorSha256':sha256((ROOT/'token_policy.py').read_bytes()).hexdigest(),'importMs':round(import_ms,3),'medianMs':round(statistics.median(samples),3),'maxMs':round(max(samples),3),'beforeImportLifetimePeakBytes':before,'afterLifetimePeakBytes':peak(),'checks':rows,'warmupExcludedFromRepeatedLatency':True,'memoryMeaning':'Owned Python process-lifetime OS peak including interpreter/imports/inputs/results, not incremental allocation or browser/model memory.','newModelCalls':0,'networkRequests':0,'newTransactions':0}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--child',choices=CASES);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.child:print(json.dumps(child(a.child)));return 0
 if a.output is None:p.error('--output is required')
 if a.output.exists():p.error('Output exists; choose a new evidence file')
 rows=[]
 for case in CASES:
  r=subprocess.run([sys.executable,'-I','-S',str(Path(__file__).resolve()),'--child',case],capture_output=True,timeout=90)
  if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-1000:])
  rows.append(json.loads(r.stdout))
 result={'format':'agent-crash-lab/policy-resources-v1','atUtc':datetime.now(timezone.utc).isoformat(),'pythonVersion':platform.python_version(),'platform':platform.platform(),'cases':rows,'meaning':'Measurements on this host/run, not performance guarantees or independent accuracy estimates.'}
 with a.output.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'measured':True,'cases':len(rows),'output':str(a.output)}));return 0

if __name__=='__main__':raise SystemExit(main())
