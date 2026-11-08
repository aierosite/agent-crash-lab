"""Replay sealed model/HTTP/SDK records. No model, SDK, signer or network starts."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from types import SimpleNamespace
import ast,copy,json,re,runpy,sys

ROOT=Path(__file__).resolve().parents[1]
STUDY_PIN='c296912ee54d4c1e24616e742300927465727f3fb590d702d3ee444a0be5750d'
pack=lambda x:json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode('utf-8')

def checked_study(root=ROOT):
 folder=Path(root).resolve()/'evidence/exposure-study';raw=(folder/'study-index.json').read_bytes()
 if sha256(raw).hexdigest()!=STUDY_PIN:raise ValueError('The recorded study index does not match this release')
 index=json.loads(raw)
 for name,meta in index['files'].items():
  path=folder/name
  if path.resolve()!=path or not path.resolve().is_relative_to(folder.resolve()):raise ValueError('Unsafe recorded study path')
  data=path.read_bytes()
  if len(data)!=meta['bytes'] or sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Recorded study bytes changed: '+name)
 return folder,index

def functions(path,names,scope):
 """Load only named, unchanged definitions from already hash-checked release code."""
 tree=ast.parse(path.read_text(encoding='utf-8'));nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
 if len(nodes)!=len(names) or {n.name for n in nodes}!=set(names):raise ValueError('Frozen reference definitions changed')
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path), 'exec'),scope)
 return scope

def readonly_audit(folder,portable):
 """Original audit definitions with explicit read-only runtime dependencies.

 Bank/decoder/rendering functions are unchanged source ASTs. HTTP/SDK process
 launch imports are not loaded. Only reference grading isolation differs.
 """
 context=json.loads((folder/'banking-context.json').read_bytes())
 bank=functions(folder/'bank_tools.py',{'cents','initial_invoice','Bank'},dict(Path=Path,Decimal=Decimal,InvalidOperation=InvalidOperation,copy=copy,json=json,re=re,H=folder,CONTEXT=context))
 tree=ast.parse((folder/'bank_loop.py').read_text(encoding='utf-8'));constants={}
 for node in tree.body:
  if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'SYSTEM','GRAMMAR'}:constants[node.targets[0].id]=ast.literal_eval(node.value)
 if set(constants)!={'SYSTEM','GRAMMAR'}:raise ValueError('Frozen caller constants changed')
 loop=functions(folder/'bank_loop.py',{'unique','decode','flat_args','initial_messages','render'},dict(json=json,pack=pack,CONTEXT=context,USER=context['prompt'],Merchant=bank['Bank'],**constants))
 def source_loader(path):
  path=Path(path)
  if path==folder/'bank_loop.py':return loop
  if path==folder/'projection.py':return runpy.run_path(str(path))
  raise ValueError('Only installed frozen reference modules may load')
 def grade_namespace(args,**kwargs):
  expected=[sys.executable,'-I','-S',str(folder/'reference_grade.py'),str(folder/'actual/episodes.json')]
  if args!=expected or kwargs!={'capture_output':True,'timeout':30,'check':True}:raise ValueError('Unsupported reference invocation')
  grader=runpy.run_path(str(folder/'reference_grade.py'))
  values=[grader['grade'](e) for e in json.loads((folder/'actual/episodes.json').read_bytes())]
  return SimpleNamespace(stdout=pack(values),stderr=b'',returncode=0)
 if portable:executor=SimpleNamespace(run=grade_namespace)
 else:
  import subprocess
  executor=subprocess
 scope=dict(Path=Path,sha256=sha256,datetime=datetime,timezone=timezone,json=json,H=folder,runpy=SimpleNamespace(run_path=source_loader),subprocess=executor,sys=SimpleNamespace(path=[],modules={},executable=sys.executable))
 auditor=functions(folder/'audit.py',{'read','audit'},scope)
 return auditor['audit'](folder)

def verified_data(root=ROOT,portable=False):
 root=Path(root).resolve();folder,index=checked_study(root);audit,grades,reports=readonly_audit(folder,portable)
 archived=json.loads((folder/'AUDIT.json').read_bytes());clock=archived.pop('auditedAtUtc');audit.pop('auditedAtUtc')
 if audit!=archived:raise ValueError('Original deterministic audit values did not reproduce')
 if grades!=json.loads((folder/'original-external-grades.json').read_bytes()) or reports!=json.loads((folder/'original-financial-reports.json').read_bytes()):raise ValueError('Original full reference and financial objects did not reproduce')
 episodes=json.loads((folder/'actual/episodes.json').read_bytes());calls=json.loads((folder/'actual/calls.json').read_bytes());plan=json.loads((folder/'REGISTRATION.json').read_bytes())
 if not (len(episodes)==len(grades)==len(reports)==6):raise ValueError('Recorded episode coverage changed')
 if [e['id'] for e in episodes]!=[e['id'] for e in plan['cases']] or [g['id'] for g in grades]!=[e['id'] for e in episodes]:raise ValueError('Recorded case identities changed')
 projection=runpy.run_path(str(folder/'projection.py'));current=runpy.run_path(str(root/'token_policy.py'))['assess'];inputs=[];current_reports=[]
 for e,original in zip(episodes,reports):
  task,evidence=projection['bundle'](e);tr,er=pack(task),pack(evidence);report=current(tr,er)
  if report!=original['report']:raise ValueError('Current payment inspector differs from the original complete report')
  inputs.append({'task_utf8':tr.decode('utf-8'),'evidence_utf8':er.decode('utf-8')});current_reports.append(report)
 return dict(folder=folder,index=index,audit=audit,grades=grades,episodes=episodes,calls=calls,paymentInputs=inputs,paymentReports=current_reports,recordedAuditorClock=clock)

def verify(root=ROOT,portable=False):
 data=verified_data(root,portable);a=data['audit']
 return {'format':'agent-crash-lab/exposure-replay-v1','mode':'same-interpreter-reference-namespace' if portable else 'separate-reference-process','study_index_sha256':STUDY_PIN,'complete_cases':a['closedTrajectories'],'returned_model_responses':a['returnedModelResponses'],'model_http_requests':a['modelSelectedHttpRequests'],'caller_prefetch_requests':a['callerReadOnlyPrefetchRequests'],'sdk_mock_effects':a['actualSdkMockEffects'],'exposed_attack_cases':a['exposedAttackCases'],'payment_gates':[r['gate'] for r in data['paymentReports']],'original_full_objects_and_current_payment_reports_matched':True,'recorded_auditor_clock':data['recordedAuditorClock'],'audit_comparison':'Every deterministic field matches; only the auditor execution-clock field is excluded. Original raw timestamps are preserved.','runtime_adaptation':'Unchanged reviewed audit/bank/caller definitions loaded without HTTP/SDK launch imports. External original predicates run in a separate process locally or a distinct namespace in the same browser interpreter.','new_model_calls':0,'new_sdk_calls':0,'new_transactions':0,'new_chain_rpc':0,'independent_blind_evaluation':False}

if __name__=='__main__':
 if sys.argv[1:] not in [[],['--portable']]:raise SystemExit('Use no arguments or --portable')
 print(json.dumps(verify(portable=bool(sys.argv[1:]))))
