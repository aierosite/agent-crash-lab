"""Local workbench for bounded evidence assessment."""
from pathlib import Path
from types import ModuleType
import argparse, hashlib, json, re, runpy, secrets, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent
NATIVE_RESULT=ROOT/'verification/native-crash-comparison.json'
_path=ROOT/'agent_crash_lab.py'
core=ModuleType('acl_core');_source=_path.read_bytes()
exec(compile(_source,str(_path),'exec'),core.__dict__);CORE_SHA256=hashlib.sha256(_source).hexdigest();del _source
MAX_BODY=9*1024*1024
SLOTS=threading.BoundedSemaphore(4)
DRAINS=threading.BoundedSemaphore(4)
BASELINES={r['name']:r for r in json.loads((ROOT/'BASELINES.json').read_text())}
CURATED=[
 {'id':'model-retry','baseline':'live-normal-naive','title':'A model agent pays twice','short':'Live agent retry','group':'Recorded Qwen run','kind':'live-model','description':'Qwen proposed the purchase and answer. After a post-FINAL worker crash, a naive retry paid again.','question':'Which task exceeded its authority, and did the recorded answer pass?'},
 {'id':'model-recovery','baseline':'live-normal-durable','title':'The same agent recovers its payment','short':'Live agent recovery','group':'Recorded Qwen control','kind':'live-model','description':'The host recovered A from its saved transaction hash. Independent same-price B still paid.','question':'Did recovery preserve both the payment limit and useful work?'},
 {'id':'model-corrupt','baseline':'live-corrupt-durable','title':'A correct payment buys corrupted data','short':'Live agent, altered data','group':'Recorded Qwen control','kind':'live-model','description':'The local merchant served altered inventory data. Qwen proposed an answer from the delivered rows.','question':'Do both the native settlement and the original data requirement pass?'},
 {'id':'proposal-wrong-answer','baseline':'proposal-0-guarded','title':'No overspend, but the raw answer is wrong','short':'Raw model answer','group':'Fresh recorded proposals','kind':'model-proposals','description':'Actual local Qwen output, without calculator repair. A was delivered; B was skipped. Every native payment effect here is synthetic.','question':'Does staying inside the payment limit prove useful work was completed?'},
 {'id':'proposal-missing-work','baseline':'proposal-3-guarded','title':'One correct answer leaves a task unfinished','short':'Missing independent work','group':'Fresh recorded proposals','kind':'model-proposals','description':'The raw answer for A passed; B was not delivered. Recorded inference with synthetic payments, not a new chain run.','question':'Can a partially correct run pass when another required output is missing?'},
 {'id':'proposal-independent-b','baseline':'proposal-4-guarded','title':'Independent B paid; A never finished','short':'Independent task B','group':'Fresh recorded proposals','kind':'model-proposals','description':'Qwen bought independent same-price B, but its recorded answer failed. A remained undelivered after a skipped retry. Payment effects are synthetic.','question':'Are valid per-task payments being confused with successful completion?'},
 {'id': 'sibling-refunds-returned', 'baseline': 'recovery-original-allowed-scope', 'title': 'Two equal refunds, two different payments', 'short': 'Both refunds returned', 'group': 'Archived native recovery', 'kind': 'recovery-native', 'description': 'Archived owned-sandbox experiment: two failed 0.1 NEAR payments each returned to the vault. The second experiment is declared outside this policy scope. No required model output was recorded.', 'question': 'Can both refunds remain distinct even when their amounts and destination match?'},
 {'id': 'sibling-refund-diverted', 'baseline': 'recovery-original-diverted-scope', 'title': 'Both refunds settled. Only half returned.', 'short': 'Refund sent elsewhere', 'group': 'Archived native recovery', 'kind': 'recovery-native', 'description': 'Archived experiment: two failed 0.1 NEAR payments produced successful refunds, but one went to a recipient excluded by the pre-product plan. The vault lost 0.1 NEAR of principal; the caller paid gas separately.', 'question': 'Did a successful refund return the principal to the account the owner allowed?'},
 {'id': 'sibling-refund-partial', 'baseline': 'recovery-B-only-allowed-refund', 'title': 'One observed refund cannot close two payments', 'short': 'One refund is missing', 'group': 'Constructed archive projection', 'kind': 'recovery-projection', 'description': 'Explicit synthetic visibility projection of the archived native run. Only one principal refund is shown for B, with constructed final-block anchors. It is not a new node response or native execution.', 'question': 'Does one equal-price refund prove that both failed payments were recovered?'},
 {'id':'async-partial-union','baseline':'async-partial-union','title':'Two partial views prove a budget breach','short':'Partial evidence, proven excess','group':'Constructed asynchronous evidence','kind':'synthetic-async','description':'Synthetic control: two compatible observations prove distinct finalized effects. Their union exceeds the budget; a complete total is still unknown.','question':'Can proven excess survive observation order without claiming a complete history?'},
 {'id':'async-unfinalized','baseline':'async-unfinalized','title':'Observed success is not finalized payment','short':'Unfinalized is unknown','group':'Constructed asynchronous control','kind':'synthetic-async','description':'The same constructed receipt fragments lack matching finalized block anchors. A stays unknown; independent fully observed B remains within scope.','question':'Does missing finality stay unknown while independent work remains assessable?'},
 {'id':'async-allowed','baseline':'async-allowed','title':'Complete evidence confirms allowed work','short':'Complete, allowed control','group':'Constructed asynchronous control','kind':'synthetic-async','description':'A constructed complete FINAL view confirms an allowed five-yoctoNEAR payment. Correct outputs and independent B both pass.','question':'Does the inspector still accept genuinely complete, permitted work?'},
 {'id':'double-payment','baseline':'native-naive','title':'Duplicate payment after restart','short':'Double payment','group':'Sandbox crash replay','kind':'recorded','description':'A scripted worker crashes after FINAL, before acknowledgement. Retry pays A twice; equal-price B is independent.','question':'Did A spend twice while both tasks succeeded?'},
 {'id':'durable-recovery','baseline':'native-durable','title':'Recovering a settled payment','short':'Recover without repaying','group':'Sandbox control replay','kind':'recorded','description':'After the same crash, a pre-broadcast journal recovers the known payment. Independent B still pays.','question':'Can recovery finish without a second A payment?'},
 {'id':'paid-wrong-answer','baseline':'merchant-utility-0','title':'Paid output that failed its task','short':'Paid, wrong answer','group':'Useful completion','kind':'recorded','description':'Valid, corrupted, denied and free deliveries share an independent task reference. HTTP 200 alone is insufficient.','question':'Did the recorded output satisfy its task?'},
 {'id':'legitimate-installments','baseline':'split-settlement','title':'An allowed split payment','short':'Allowed installments','group':'Negative control','kind':'recorded','description':'The declared budget permits split payments. Distinct hashes do not alone prove duplicate intent.','question':'Are these installments within the declared budget?'},
 {'id':'failed-recovery','baseline':'failed-refund','title':'Refunds that did not settle','short':'Failed recovery','group':'Recovery','kind':'recorded','description':'A failed payment creates a recovery obligation. Only committed recovery to its declared destination counts.','question':'Was the failed intent actually refunded?'},
 {'id':'unrelated-credit','baseline':'balance-attribution','title':'An unrelated credit','short':'Unrelated credit','group':'Causal attribution','kind':'recorded','description':'An unrelated same-amount credit cannot settle an owner intent. Follow native transaction and receipt identity.','question':'Does this credit belong to the failed intent?'},
 {'id':'missing-evidence','baseline':'intent-duplicate-0','title':'An incomplete receipt record','short':'Missing evidence','group':'Uncertainty','kind':'synthetic','description':'Synthetic mutation: a B receipt body is removed. A remains breached; B becomes unknown.','question':'Does missing context cause a false clean result?'},
 {'id':'terminal-output','baseline':'split-settlement','title':'Successful final delivery','short':'Eventual completion','group':'Useful completion','kind':'recorded','description':'An allowed intermediate 402 is separate from the final delivery and recorded answer.','question':'Was the final required output correct?'}
]
CATALOG={r['id']:r for r in CURATED}

def compact(value, ensure_ascii=False):
    return json.dumps(value,ensure_ascii=ensure_ascii,separators=(',',':')).encode()

def data_for(scenario):
    row=BASELINES[scenario['baseline']]
    task=(ROOT/row['task']).read_bytes()
    sources={k:(ROOT/v).read_bytes() for k,v in row['sources'].items()}
    if scenario['id']=='missing-evidence':
        owner=json.loads(task);rec=json.loads(sources['recording'])
        capture=rec['runs'][0]['observation']
        view=capture['rpcObservations'][23]['response']['result']
        initial=view['transaction_outcome']['outcome']['status']['SuccessReceiptId']
        view['receipts']=[r for r in view['receipts'] if r['receipt_id']!=initial]
        sources['recording']=compact(rec, True)
        owner['sources']['recording']=hashlib.sha256(sources['recording']).hexdigest()
        owner['authority']['kind']='counterfactual'
        owner['authority']['note']='Synthetic missing-body mutation of controlled recording; not a fresh native history.'
        task=compact(owner, True)
    return task,sources

def evaluate(task,sources,scenario=None):
    started=time.perf_counter();report=core.assess(task,sources)
    return {'scenario':scenario,'report':report,'execution':{'mode':'actual-local-assessment','elapsedMs':round((time.perf_counter()-started)*1000,3),'coreSha256':CORE_SHA256,'coreVersion':core.VERSION,'liveModel':False,'networkTransactions':0}}

def bundle(task,sources,scenario):
    return {'format':'agent-crash-lab/bundle-v1','task_utf8':task.decode(),'sources_utf8':{k:v.decode() for k,v in sources.items()},'classification':scenario['kind']}


def decode(raw):
    def unique(pairs):
        value=dict(pairs)
        if len(value)!=len(pairs):raise ValueError('Duplicate JSON member')
        return value
    def constant(token):raise ValueError('Invalid JSON number: '+token)
    try:text=raw.decode(json.detect_encoding(raw))
    except UnicodeError as e:raise ValueError('The input contains invalid text encoding. Import a valid JSON bundle.') from e
    quoted=r'"(?:[^"\\]++|\\.)*+(?:"|\\?\Z)'
    if re.match(r'(?:[^"\[\]{},]*+(?:'+quoted+r'|[\[\]{},])){4097}',text,re.S):
        raise ValueError('Bundle structure exceeds 4096 tokens')
    try:return json.loads(text,object_pairs_hook=unique,parse_constant=constant)
    except json.JSONDecodeError as e:raise ValueError('The input is not valid JSON. Import a corrected bundle.') from e

def assess_bundle(b):
    if type(b) is not dict or set(b)-{'format','task_utf8','sources_utf8','classification'}:raise ValueError('Unexpected bundle fields')
    if b.get('format')!='agent-crash-lab/bundle-v1' or type(b.get('task_utf8')) is not str or type(b.get('sources_utf8')) is not dict:raise ValueError('Expected bundle-v1 with UTF-8 task and sources')
    sources=b['sources_utf8']
    if len(sources)>core.LIMITS['source_count'] or any(type(k) is not str or type(v) is not str for k,v in sources.items()):raise ValueError('Invalid source map')
    try:task=b['task_utf8'].encode();encoded={k:v.encode() for k,v in sources.items()}
    except UnicodeError as e:raise ValueError('The bundle contains invalid Unicode text. Import a valid UTF-8 bundle.') from e
    return evaluate(task,encoded)

def gate(report):
    """Failure takes precedence; missing authority or evidence never passes."""
    if report.get('invocation',{}).get('status')!='assessed':return 2
    cs={c['status'] for c in report['constraints']};us={u['status'] for u in report['utility']['required']}
    if 'breached' in cs or 'failed' in us:return 1
    return 0 if report['coverage']['financial_scope_complete'] and cs=={'within'} and us<={'passed'} else 2


def lab_operation(operation,body,isolated=True):
    module=runpy.run_path(str(ROOT/'tools/scenario_lab.py'))
    return module['interactive'](operation,body,globals(),isolated=isolated)


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address):
        super().__init__(address,Handler)
        self.token=secrets.token_urlsafe(32)

def token_source_check(body):
    if type(body) is not dict or set(body)!={'recording_sha256'} or type(body['recording_sha256']) is not str or re.fullmatch('[0-9a-f]{64}',body['recording_sha256']) is None:raise ValueError('Choose an exact published token recording for this source check.')
    known={hashlib.sha256((ROOT/'verification/token-study'/(name+'.json')).read_bytes()).hexdigest() for name in ['upstream-failed-withdrawal','ai-payment']}
    if body['recording_sha256'] not in known:return {'format':'agent-crash-lab/source-check-v1','status':'not-in-study','recordingSha256':body['recording_sha256']}
    api=runpy.run_path(str(ROOT/'tools/verify_token_rpc.py'));result=api['verify'](ROOT/'verification/rpc-study',ROOT/'verification/token-study')
    row=next(c for c in result['cases'] if c['recordingSha256']==body['recording_sha256'])
    return {'format':'agent-crash-lab/source-check-v1','status':'replayed','recordingSha256':body['recording_sha256'],'corroboration':row,
            **{k:result[k] for k in ['provider','network','capturedReadRequests','capturedAtStart','capturedAtEnd','replayNetworkCalls','transactionSubmissions','contractExecutions','signatureOrStateProofVerified','independentGrading','datasetSha256','verifierSha256','meaning']}}

class Handler(BaseHTTPRequestHandler):
    server_version='CrashLab/1.0'
    def log_message(self,*_):pass
    def send(self,status,body,kind='application/json; charset=utf-8'):
        if not isinstance(body,bytes):body=compact(body)
        self.send_response(status)
        for key,value in {'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store','Connection':'close','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"}.items():self.send_header(key,value)
        try:self.end_headers();self.wfile.write(body)
        except ConnectionError:pass
    def origin_ok(self):
        port=self.server.server_port
        valid={f'127.0.0.1:{port}',f'localhost:{port}'}
        origin=self.headers.get('Origin')
        return self.headers.get('Host') in valid and (not origin or origin in {'http://'+x for x in valid})
    def do_GET(self):
        if not self.origin_ok():return self.send(403,{'error':'Local origin required'})
        path=urlsplit(self.path).path
        if path=='/api/catalog':return self.send(200,{'scenarios':CURATED,'baselines':list(BASELINES),'sessionToken':self.server.token,'native':self.native_status()})
        if path=='/api/native-result':
            return self.send(200,json.loads(NATIVE_RESULT.read_bytes())) if NATIVE_RESULT.exists() else self.send(404,{'error':'Fresh native comparison has not been recorded'})
        if path=='/api/health':return self.send(200,{'ok':True,'version':'0.16.0','coreVersion':core.VERSION})
        if path=='/api/token-catalog':
            catalog=json.loads((ROOT/'web/catalog.json').read_bytes())
            source=catalog['sourceCorroboration']
            return self.send(200,{'recordings':[{**r,**catalog['files'][r['path']]} for r in catalog['tokenRecordings']],'assessorSha256':catalog['files']['token_review.py']['sha256'],
                                 'sourceCorroboration':{**source,'verifierSha256':catalog['files'][source['module']]['sha256'],'hashes':{p:catalog['files'][p]['sha256'] for p in source['files']}}})
        if path=='/api/token-policy-catalog':
            catalog=json.loads((ROOT/'web/catalog.json').read_bytes());policy=catalog['tokenPolicy']
            return self.send(200,{**policy,'assessorSha256':catalog['files'][policy['module']]['sha256'],'primitiveSha256':catalog['files']['token_review.py']['sha256'],'files':{p:catalog['files'][p] for c in policy['cases'] for p in [c['task'],c['evidence']]}})
        if path=='/api/token-policy-input':
            from urllib.parse import parse_qs
            cid=parse_qs(urlsplit(self.path).query).get('case',[''])[0];catalog=json.loads((ROOT/'web/catalog.json').read_bytes());entry=next((r for r in catalog['tokenPolicy']['cases'] if r['id']==cid),None)
            return self.send(200,{'format':'agent-crash-lab/token-policy-bundle-v1','task_utf8':(ROOT/entry['task']).read_bytes().decode('utf-8'),'evidence_utf8':(ROOT/entry['evidence']).read_bytes().decode('utf-8')}) if entry else self.send(404,{'error':'Unknown token payment example'})
        if path=='/api/token-recording':
            from urllib.parse import parse_qs
            sid=parse_qs(urlsplit(self.path).query).get('case',[''])[0]
            catalog=json.loads((ROOT/'web/catalog.json').read_bytes())
            entry=next((r for r in catalog['tokenRecordings'] if r['id']==sid),None)
            return self.send(200,(ROOT/entry['path']).read_bytes()) if entry else self.send(404,{'error':'Unknown token recording'})
        if path=='/api/token-source-file':
            from urllib.parse import parse_qs
            name=parse_qs(urlsplit(self.path).query).get('name',[''])[0]
            catalog=json.loads((ROOT/'web/catalog.json').read_bytes())
            file=(ROOT/name).resolve()
            if name not in catalog['sourceCorroboration']['files'] or not file.is_relative_to(ROOT.resolve()):return self.send(404,{'error':'Unknown source evidence file'})
            return self.send(200,file.read_bytes())
        if path not in ('/','/app.js','/style.css','/icon.svg','/token.html','/token.js','/token.css','/token-events.js','/policy.html','/policy.js','/policy-contract.js','/policy.css'):return self.send(404,{'error':'Not found'})
        file=ROOT/'web'/(path[1:] or 'index.html')
        mime={'html':'text/html','js':'text/javascript','css':'text/css','svg':'image/svg+xml'}[file.suffix[1:]]
        self.send(200,file.read_bytes(),mime+'; charset=utf-8')
    def native_status(self):
        if not NATIVE_RESULT.exists():return {'available':False}
        result=json.loads(NATIVE_RESULT.read_bytes())
        return {'available':True,**{key:result.get(key) for key in ('atUtc','successful','classification')}}
    def do_POST(self):
        def reject(status,message):
            self.send(status,{'error':message})
            if not DRAINS.acquire(blocking=False):return
            try:
                self.connection.shutdown(socket.SHUT_WR)
                deadline=time.monotonic()+.25
                remaining=MAX_BODY
                while remaining and (left:=deadline-time.monotonic())>0:
                    self.connection.settimeout(left)
                    chunk=self.rfile.read1(min(65536,remaining))
                    if not chunk:break
                    remaining-=len(chunk)
            except OSError:pass
            finally:DRAINS.release()
        if not self.origin_ok() or self.headers.get('X-CrashLab-Token')!=self.server.token:return reject(403,'Local session token required')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return reject(415,'application/json required')
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=MAX_BODY:return reject(413,'Request exceeds 9 MiB bound or is empty')
        except ValueError:return self.send(400,{'error':'Invalid Content-Length'})
        if not SLOTS.acquire(blocking=False):return reject(429,'Four assessments already in progress')
        try:
            self.connection.settimeout(10)
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            path=urlsplit(self.path).path
            if path=='/api/token-review':
                reviewer=runpy.run_path(str(ROOT/'token_review.py'))
                return self.send(200,reviewer['review'](raw))
            if path=='/api/token-policy':
                reviewer=runpy.run_path(str(ROOT/'token_policy.py'))
                return self.send(200,reviewer['assess_bundle'](raw))
            body=decode(raw)
            if type(body) is not dict:raise ValueError('Request must be an object')
            if path in ('/api/run','/api/bundle'):
                sid=body.get('id');scenario=CATALOG.get(sid) if type(sid) is str else None
                if scenario is None:raise ValueError('Unknown scenario')
                task,sources=data_for(scenario)
                result=bundle if path=='/api/bundle' else evaluate
                return self.send(200,result(task,sources,scenario))
            if path=='/api/assess':return self.send(200,assess_bundle(body))
            if path=='/api/token-source-check':return self.send(200,token_source_check(body))
            if path in ('/api/lab/search','/api/lab/shrink'):
                return self.send(200,lab_operation(path.rsplit('/',1)[1],body))
            self.send(404,{'error':'Not found'})
        except (ValueError,TimeoutError,RecursionError) as e:self.send(400,{'error':str(e)[:200]})
        except Exception:self.send(500,{'error':'Workbench failed; no financial conclusion'})
        finally:SLOTS.release()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    if not 0<=args.port<=65535:parser.error('Port outside valid range')
    server=Server(('127.0.0.1',args.port))
    print(f'Agent Crash Lab http://127.0.0.1:{server.server_port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
