from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import argparse,base64,json,subprocess
H=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--set',type=int,required=True,choices=[1,2]);a=p.parse_args();reg=json.loads((H/'REGISTRATION.json').read_bytes())
require_source={'runner/src/main.rs':reg['harnessSourceSha256'],'runner/Cargo.lock':reg['lockSha256'],'journal_review.py':reg['assessorSha256'],'financial_reference.py':reg['financialReferenceSha256']}
for name,digest in require_source.items():assert sha256((H/name).read_bytes()).hexdigest()==digest,name
assert sha256(Path(__file__).read_bytes()).hexdigest()==reg['executionDriverSha256']
if a.case=='baseline':input_name='inputs/baseline.json';expected_sha=reg['baselineInputSha256'];point=None
else:
    point=next(x for x in reg['faultPoints'] if x['id']==a.case);input_name=point['input'];expected_sha=point['inputSha256']
raw=(H/input_name).read_bytes();assert sha256(raw).hexdigest()==expected_sha
label=a.case+'-set-'+str(a.set);assert not (H/(label+'.json')).exists() and not (H/(label+'.process.json')).exists()
linux=r'''
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,base64,subprocess,time,os,signal,resource
d=json.loads(__import__('sys').stdin.read());r=Path('/tmp/agent-crash-lab-receipt-crash-v019');prior=Path('/tmp/agent-crash-lab-receipt-v019');binary=prior/'target/debug/crash-lab-receipt-crash-research';label=d['label'];point=d['point'];journal=r/'journals'/(label+'.jsonl');procfile=r/(label+'.process.json')
assert not journal.exists() and not procfile.exists()
assert sha256(binary.read_bytes()).hexdigest()==d['binarySha256'] and sha256((r/'runner/src/main.rs').read_bytes()).hexdigest()==d['harnessSourceSha256']
assert sha256((r/'runner/Cargo.lock').read_bytes()).hexdigest()==d['lockSha256']
raw=(r/d['inputName']).read_bytes();assert sha256(raw).hexdigest()==d['inputSha256']
args=[str(binary),'--journal',str(journal)]
if point is not None:args+=['--pause-after',point['argument']]
probe='import os,json,sys;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({"net":os.readlink("/proc/self/ns/net"),"pid":os.getpid()}));os.execv(sys.argv[2],sys.argv[2:])'
namespace=r/(label+'.namespace.json');env=os.environ.copy();env['RAYON_NUM_THREADS']='1';start=time.monotonic();child=subprocess.Popen(['unshare','--net','--','python3','-I','-S','-c',probe,str(namespace),*args],cwd=r,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
procfile.write_text(json.dumps({'pid':child.pid,'label':label,'binary':str(binary),'cwd':str(r),'timeoutSeconds':120}))
sent=False;kill=None;stopped=None;peak=0;out=err=b''
while True:
    try:out,err=child.communicate(input=None if sent else raw,timeout=0.1);break
    except subprocess.TimeoutExpired:
        sent=True
        status=Path(f'/proc/{child.pid}/status')
        if status.exists():
            for line in status.read_text().splitlines():
                if line.startswith('VmRSS:'):peak=max(peak,int(line.split()[1]))
        if point is not None and journal.exists():
            journal_bytes=journal.read_bytes();lines=journal_bytes.splitlines()
            if journal_bytes.endswith(b'\n') and lines:
                try:last=json.loads(lines[-1])
                except json.JSONDecodeError:last=None
                expected={'case':point['case'],'step':point['step'],'round':point['round'],'mode':'sync_data_then_cooperative_pause_for_external_sigkill'}
                if last is not None and last.get('event')=='research_fault_checkpoint' and last.get('data')==expected:
                    pid=child.pid;proc=Path('/proc')/str(pid)
                    actual_exe=proc.joinpath('exe').resolve();actual_cwd=proc.joinpath('cwd').resolve();argv=proc.joinpath('cmdline').read_bytes().split(b'\0')[:-1]
                    assert child.poll() is None and actual_exe==binary.resolve() and actual_cwd==r.resolve() and os.getpgid(pid)==pid
                    assert argv==[x.encode() for x in args]
                    net=os.readlink(proc/'ns/net');assert net!=os.readlink('/proc/self/ns/net')
                    kill={'atUtc':datetime.now(timezone.utc).isoformat(),'pid':pid,'pgid':os.getpgid(pid),'exe':str(actual_exe),'cwd':str(actual_cwd),'argv':[x.decode() for x in argv],'namespace':net,'checkpoint':last,'preKillJournalSha256':sha256(journal_bytes).hexdigest(),'signal':'SIGKILL'}
                    os.killpg(pid,signal.SIGKILL);out,err=child.communicate(timeout=10);break
        if time.monotonic()-start>120:stopped='wall-clock limit'
        if peak>2*1024**2:stopped='observed child RSS above2GiB'
        if stopped:
            os.killpg(child.pid,signal.SIGTERM)
            try:out,err=child.communicate(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);out,err=child.communicate(timeout=5)
            break
journal_bytes=journal.read_bytes() if journal.exists() else b''
result={'label':label,'exitCode':child.returncode,'elapsedSeconds':time.monotonic()-start,'observedPeakLeaderRssKiB':peak,'maxChildRssKiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'kill':kill,'stoppedReason':stopped,'namespace':json.loads(namespace.read_bytes()) if namespace.exists() else None,'parentNamespace':os.readlink('/proc/self/ns/net'),'journalSurvivesProcessExit':bool(journal_bytes),'journalUnchangedAfterKill':kill is not None and sha256(journal_bytes).hexdigest()==kill['preKillJournalSha256'],'sourceAndInputUnchanged':sha256((r/'runner/src/main.rs').read_bytes()).hexdigest()==d['harnessSourceSha256'] and sha256((r/d['inputName']).read_bytes()).hexdigest()==d['inputSha256'],'upstreamGitStatus':subprocess.check_output(['git','-C',str(prior/'upstream'),'status','--porcelain'],text=True),'stdout':base64.b64encode(out).decode(),'stderr':base64.b64encode(err).decode(),'journal':base64.b64encode(journal_bytes).decode()}
(r/(label+'.json')).write_text(json.dumps(result));print(json.dumps(result))
'''
payload={'label':label,'point':point,'inputName':input_name,'inputSha256':expected_sha,'binarySha256':reg['binarySha256'],'harnessSourceSha256':reg['harnessSourceSha256'],'lockSha256':reg['lockSha256']}
child=subprocess.Popen(['wsl','-d','Gamero-Unified-QA-20261028','-e','python3','-I','-S','-c',linux],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
(H/(label+'.process.json')).write_text(json.dumps({'startedAtUtc':datetime.now(timezone.utc).isoformat(),'ownedWindowsWslPid':child.pid,'inputSha256':expected_sha,'registrationSha256':sha256((H/'REGISTRATION.json').read_bytes()).hexdigest()},indent=2)+'\n')
print(json.dumps({'experimentStarted':label,'ownedWindowsWslPid':child.pid}),flush=True);sent=False
while True:
    try:out,err=child.communicate(input=None if sent else json.dumps(payload).encode(),timeout=20);break
    except subprocess.TimeoutExpired:sent=True;print(json.dumps({'experimentLive':label,'ownedWindowsWslPid':child.pid}),flush=True)
(H/(label+'.driver.stdout.json')).write_bytes(out);(H/(label+'.driver.stderr.txt')).write_bytes(err);assert child.returncode==0,err[-4000:]
d=json.loads(out);d['atUtc']=datetime.now(timezone.utc).isoformat();d['registrationSha256']=sha256((H/'REGISTRATION.json').read_bytes()).hexdigest()
for stream,extension in [('stdout','json'),('stderr','txt'),('journal','jsonl')]:
    raw=base64.b64decode(d.pop(stream));(H/(label+'.'+stream+'.'+extension)).write_bytes(raw);d[stream+'Bytes']=len(raw);d[stream+'Sha256']=sha256(raw).hexdigest()
(H/(label+'.json')).write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
assert d['sourceAndInputUnchanged'] and not d['upstreamGitStatus'] and d['stoppedReason'] is None
assert d['namespace']['net']!=d['parentNamespace']
if point is None:assert d['exitCode']==0 and d['kill'] is None
else:assert d['exitCode']==-9 and d['kill'] is not None and d['journalUnchangedAfterKill'] and d['stdoutBytes']==0
print(json.dumps({k:v for k,v in d.items() if k!='kill'}),flush=True)
