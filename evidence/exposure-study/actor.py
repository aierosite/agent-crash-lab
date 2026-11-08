"""Registered actual local inference with explicit read-only context delivery."""
from pathlib import Path
from hashlib import sha256,file_digest
from datetime import datetime,timezone
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
import json,os,signal,socket,subprocess,sys,tarfile,threading,time
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
from bank_loop import Sdk,Merchant,serve,pack,decode,drive,GRAMMAR,render
utc=lambda:datetime.now(timezone.utc).isoformat()
def digest(p):
 with Path(p).open('rb') as stream:return file_digest(stream,'sha256').hexdigest()
def save(p,value):
 temp=p.with_name(p.name+'.tmp');temp.write_bytes(pack(value)+b'\n');temp.replace(p)

def main():
 plan=decode((H/'REGISTRATION.json').read_bytes());lock=decode((H/'LOCK.json').read_bytes());out=H/'actual';out.mkdir(exist_ok=False)
 calls=[];episodes=[];proc=None;sdk=None;server=None;thread=None;log=None;sdk_log=None;failure=None;peaks={};stop=threading.Event();observer=None
 started=time.monotonic();deadline=started+plan['limits']['batchSeconds'];http=build_opener(ProxyHandler({}));endpoint=None
 def unchanged():return all(digest(H/n)==v['sha256'] for n,v in lock['sources'].items())
 save(out/'run.json',{'startedAtUtc':utc(),'lockSha256':digest(H/'LOCK.json'),'registrationSha256':digest(H/'REGISTRATION.json'),'status':'started'})
 def complete(case,turn,messages):
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

 try:
  assert sys.platform=='linux' and unchanged() and digest(H/'REGISTRATION.json')==lock['registrationSha256']
  model=H/'model.gguf';archive=H/'runtime.tar.gz';sdk_binary=Path('/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-banking-sdk')
  assert digest(model)==plan['model']['sha256'] and digest(archive)==plan['runtime']['sha256'] and digest(sdk_binary)==decode((H/'BUILD.json').read_bytes())['sdkBinarySha256']
  target=out/'runtime';target.mkdir()
  with tarfile.open(archive) as bundle:
   members=bundle.getmembers();assert len(members)<200 and sum(max(0,x.size) for x in members)<256*1024**2;bundle.extractall(target,filter='data')
  bins=list(target.rglob('llama-server'));assert len(bins)==1;binary=bins[0];assert digest(binary)==plan['runtime']['binarySha256']
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  endpoint='http://127.0.0.1:'+str(port);log=(out/'runtime.log').open('wb');sdk_log=(out/'sdk.log').open('wb')
  sdk=Sdk(sdk_binary,sdk_log)
  merchant=Merchant(sdk);server,thread=serve(merchant);origin='http://127.0.0.1:'+str(server.server_port)
  command=[str(binary),'-m',str(model),'--jinja','--no-context-shift','--host','127.0.0.1','--port',str(port),'-c','8192','-t','2','-tb','2','-ngl','0','--parallel','1']
  proc=subprocess.Popen(command,stdout=log,stderr=log,env={'PATH':os.defpath,'LANG':'C.UTF-8','LD_LIBRARY_PATH':str(binary.parent)},start_new_session=True)
  save(out/'server.json',{'command':command,'modelPid':proc.pid,'sdkPid':sdk.process.pid,'endpoint':endpoint,'merchantEndpoint':origin,'binarySha256':digest(binary),'sdkBinarySha256':digest(sdk_binary)})
  def observe():
   while not stop.wait(.1):
    for name,pid in [('model',proc.pid),('sdk',sdk.process.pid)]:
     try:
      line=next(x for x in Path('/proc/'+str(pid)+'/status').read_text(encoding='utf-8').splitlines() if x.startswith('VmHWM:'));peaks[name]=max(peaks.get(name,0),int(line.split()[1])*1024)
     except (OSError,StopIteration):pass
  observer=threading.Thread(target=observe,daemon=True);observer.start();ready_start=time.monotonic()
  while True:
   if proc.poll() is not None or time.monotonic()-ready_start>90:raise RuntimeError('Owned model startup failed')
   try:
    with http.open(endpoint+'/health',timeout=2) as response:
     if decode(response.read())['status']=='ok':break
   except OSError:pass
   time.sleep(.2)
  with http.open(endpoint+'/props',timeout=5) as response:props=response.read(131073)
  assert len(props)<=131072 and decode(props)['build_info']=='b12110-cd959bae9';(out/'model-properties.json').write_bytes(props)
  for case in plan['cases']:
   episodes.append({**case,'executionComplete':False})
   def checkpoint(value):episodes[-1]=json.loads(pack(value));save(out/'episodes.json',episodes);save(out/'sdk-wire.json',sdk.requests)
   drive(case,merchant,origin,complete,checkpoint)
   print(json.dumps({'phase':'trajectory-complete','case':case['id'],'calls':len(calls),'finished':episodes[-1]['finished'],'sdkEffects':len(merchant.sdk_rows)}),flush=True)
 except BaseException as error:failure=type(error).__name__+': '+str(error)
 finally:
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(5)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(3)
  stop.set()
  if observer:observer.join(2)
  if server:server.shutdown();server.server_close()
  if thread:thread.join(2)
  if sdk:sdk.close();save(out/'sdk-wire.json',sdk.requests)
  if log:log.close()
  if sdk_log:sdk_log.close()
  save(out/'calls.json',calls);save(out/'episodes.json',episodes)
  result={'complete':failure is None and len(episodes)==len(plan['cases']) and all(e['executionComplete'] for e in episodes),'failure':failure,'casesPlanned':len(plan['cases']),'casesStarted':len(episodes),'casesComplete':sum(bool(e.get('executionComplete')) for e in episodes),'evaluationCalls':len(calls),'returnedCalls':sum(c['state']=='complete' for c in calls),'warmupCalls':0,'sourceHashesUnchanged':unchanged(),'ownedModelStopped':proc is None or proc.poll() is not None,'ownedSdkStopped':sdk is None or sdk.process.poll() is not None,'elapsedSeconds':round(time.monotonic()-started,3),'peakSampledProcessVmHwmBytes':peaks,'finishedAtUtc':utc(),'newTransactions':0,'newChainRpc':0,'externalModelCalls':0}
  save(out/'execution.json',result);print(json.dumps(result),flush=True)
 return 0 if result['complete'] else 1

if __name__=='__main__':raise SystemExit(main())
