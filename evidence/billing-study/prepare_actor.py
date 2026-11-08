from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json
H=Path(__file__).resolve().parent;old=H.parent/'banking-agent-study-v015/actor.py';text=old.read_text(encoding='utf-8');assert not (H/'actor.py').exists()
before='from bank_loop import Sdk,Merchant,serve,pack,decode,drive,TOOLS';assert text.count(before)==1;text=text.replace(before,'from bank_loop import Sdk,Merchant,serve,pack,decode,drive,GRAMMAR,render')
start=text.index(' def complete(case,turn,messages):');end=text.index('\n try:\n  assert sys.platform',start);old_complete=text[start:end]
replacement=''' def complete(case,turn,messages):
  if time.monotonic()>=deadline or len(calls)>=plan['limits']['maxEvaluationCalls']:raise TimeoutError('Fixed registered time/call limit')
  prompt=render(messages);request={'prompt':prompt,'grammar':GRAMMAR,'temperature':.2,'seed':case['seed'],'n_predict':256,'cache_prompt':False,'stop':['<|im_end|>']};body=pack(request)
  if len(body)>262144:raise ValueError('Full request exceeds quota; no history trimming')
  row={'id':len(calls),'case':case['id'],'turn':turn,'warmup':False,'startedAtUtc':utc(),'state':'started','wireRequest':json.loads(body),'requestSha256':sha256(body).hexdigest(),'inferenceRequestStarted':False};calls.append(row);save(out/'calls.json',calls)
  with http.open(Request(endpoint+'/tokenize',pack({'content':prompt,'add_special':False,'parse_special':True}),{'Content-Type':'application/json'}),timeout=10) as response:tokens=response.read(262145)
  row['tokenizerResponseUtf8']=tokens.decode('utf-8');row['promptTokens']=len(decode(tokens)['tokens'])
  if row['promptTokens']>7800:raise ValueError('Full prompt exceeds context quota; no history trimming')
  row['inferenceRequestStarted']=True;save(out/'calls.json',calls);t=time.monotonic()
  try:
   with http.open(Request(endpoint+'/completion',body,{'Content-Type':'application/json'}),timeout=min(plan['limits']['perCallSeconds'],deadline-time.monotonic())) as response:reply=response.read(262145);row['httpStatus']=response.status
  except HTTPError as error:
   reply=error.read(262145);row.update(httpStatus=error.code,responseUtf8=reply.decode('utf-8',errors='replace'),state='error');error.close();save(out/'calls.json',calls);raise RuntimeError('Model HTTP rejection; original error preserved')
  row.update(responseUtf8=reply.decode('utf-8'),responseSha256=sha256(reply).hexdigest(),elapsedMs=round((time.monotonic()-t)*1000,3),state='returned');save(out/'calls.json',calls)
  if len(reply)>262144:raise ValueError('Model response quota')
  value=decode(reply);n=value.get('tokens_predicted',value.get('timings',{}).get('predicted_n'));row.update(content=value.get('content'),tokensGenerated=n,stopped_limit=value.get('stop_type')=='limit',stopType=value.get('stop_type'))
  if type(n) is not int or not 0<n<=256 or type(row['content']) is not str:raise ValueError('Missing actual generated text/tokens')
  if value.get('truncated') or value.get('stop_type') not in ['eos','word']:raise ValueError('Context/output budget; no truncation repair')
  row.update(state='complete',finishedAtUtc=utc());save(out/'calls.json',calls);return row
'''
text=text[:start]+replacement+text[end:];(H/'actor.py').write_text(text,encoding='utf-8',newline='\n')
(H/'ACTOR-ADAPTATION.json').write_text(json.dumps({'atUtc':datetime.now(timezone.utc).isoformat(),'baseSource':'banking-agent-study-v015/actor.py','baseSha256':sha256(old.read_bytes()).hexdigest(),'oldCompleteFunctionSha256':sha256(old_complete.encode('utf-8')).hexdigest(),'newCompleteFunctionSha256':sha256(replacement.encode('utf-8')).hexdigest(),'change':'Full ChatML prompt, generic JSON grammar, exact raw completion/tokens/stop state; same runtime/model/SDK lifecycle and independent-reference-free actor. No output repair or business-value filling.'},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'actorPrepared':True,'inferenceCalls':0}))
