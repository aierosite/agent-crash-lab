"""Offline frozen/current replay of the recorded real-model/HTTP/SDK mock study."""
from pathlib import Path
from hashlib import sha256
import json,runpy,shutil,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/agent-loop-study'
INDEX='33be1c9086bf3b46184619ae061104f9709a685a3d6901b20b5277377c8e9e07'

def verify():
 raw=(DATA/'study-index.json').read_bytes()
 if sha256(raw).hexdigest()!=INDEX:raise ValueError('Recorded agent study inventory changed')
 index=json.loads(raw)
 for name,expected in index['files'].items():
  path=DATA/name
  if not path.resolve().is_relative_to(DATA.resolve()):raise ValueError('Unsafe study path')
  body=path.read_bytes()
  if len(body)!=expected['bytes'] or sha256(body).hexdigest()!=expected['sha256']:raise ValueError('Recorded study bytes differ: '+name)
 with tempfile.TemporaryDirectory(prefix='crash-lab-agent-replay-') as directory:
  target=Path(directory)
  for name in index['files']:
   dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DATA/name,dest)
  process=subprocess.run([sys.executable,'-I','-S',str(target/'audit_actual.py')],capture_output=True,timeout=30)
  if process.returncode:raise ValueError('Frozen interaction audit failed: '+process.stderr.decode(errors='replace')[-700:])
  for name in ['AUDIT.json','original-external-grades.json','original-financial-reports.json']:
   actual=(target/name).read_bytes();recorded=(DATA/name).read_bytes()
   if json.loads(actual)!=json.loads(recorded) or actual.replace(b'\r\n',b'\n')!=recorded.replace(b'\r\n',b'\n'):raise ValueError('Original recorded result did not reproduce: '+name)
 summary=json.loads((DATA/'AUDIT.json').read_bytes());episodes=json.loads((DATA/'actual/episodes.json').read_bytes())
 original=json.loads((DATA/'original-financial-reports.json').read_bytes());adapter=runpy.run_path(str(DATA/'assess_episode.py'))
 inspect=runpy.run_path(str(ROOT/'token_policy.py'))['assess'];current=[]
 for episode,old in zip(episodes,original):
  task,evidence=adapter['bundle'](episode);report=inspect(adapter['pack'](task),adapter['pack'](evidence))
  if old['invoked']:
   expected={**old['report'],'assessor_sha256':report['assessor_sha256']}
   if report!=expected:raise ValueError('Current payment projection differs: '+episode['id'])
  elif report['gate']!=2 or report['graphs'] or report['payments'] or any(i['gross_exact'] is not None or i['settled_exact'] is not None for i in report['intents']):
   raise ValueError('Empty actual payment evidence must stay unknown: '+episode['id'])
  current.append({'id':episode['id'],'gate':report['gate'],'report':report})
 return {'format':'agent-crash-lab/agent-loop-replay-v1','mode':'offline-recorded-execution-replay',
  'recordedTrajectories':summary['actualTrajectories'],'recordedEvaluationCalls':summary['evaluationCalls'],
  'recordedWarmupCalls':summary['warmupCalls'],'recordedHttpRequests':summary['actualHttpToolRequests'],
  'recordedSdkMockEffects':summary['actualSdkMockEffects'],'utilityStatuses':summary['utilityStatuses'],
  'byPolicy':summary['byPolicy'],'originalReportsReproduced':len(original),
  'currentFinancialGates':{str(g):sum(x['gate']==g for x in current) for g in [0,1,2]},
  'emptyCasesNowStructuredUnknown':sum(not x['invoked'] for x in original),
  'newModelCalls':0,'newTransactions':0,'newRpc':0,'independentBlindEvaluation':False,
  'replayComparison':'Original bytes pinned by the study index; reproduced full JSON values and serialization match, allowing only platform CRLF/LF line endings.',
  'meaning':'Saved real CPU inference and HTTP/SDK mock effects, with externally authored GSM8K numeric grading. The environment, selection, receipt adapter and financial reference are ours. Replay launches no model, merchant or SDK worker; this is not deployed-WASM/network execution, an unseen benchmark or population guard-benefit estimate.'}

if __name__=='__main__':print(json.dumps(verify()))
