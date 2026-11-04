"""Local, bounded workbench. It assesses bytes; it never signs or sends funds."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, secrets, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('acl_core',ROOT/'agent_crash_lab.py')
core=importlib.util.module_from_spec(_spec);_source=(ROOT/'agent_crash_lab.py').read_bytes()
exec(compile(_source,_spec.origin,'exec'),core.__dict__);CORE_SHA256=hashlib.sha256(_source).hexdigest();del _source
MAX_BODY=9*1024*1024
SLOTS=threading.BoundedSemaphore(4)
BASELINES={r['name']:r for r in json.loads((ROOT/'BASELINES.json').read_text())}
CURATED=[
 {'id':'double-payment','baseline':'intent-duplicate-0','title':'Duplicate payment after restart','short':'Double payment','group':'Payment integrity','kind':'recorded','description':'Intent A gets the right inventory answer, but two distinct transactions settle twice. Equal-price intent B is legitimate.','question':'Did the agent finish the task within its own payment authority?'},
 {'id':'paid-wrong-answer','baseline':'merchant-utility-0','title':'Paid output that failed its task','short':'Paid, wrong answer','group':'Useful completion','kind':'recorded','description':'Compare valid paid content, corrupted paid content, denied delivery and a permitted free source. A 200 response is not useful completion.','question':'Did the purchased output actually satisfy the declared task?'},
 {'id':'legitimate-installments','baseline':'split-settlement','title':'An allowed split payment','short':'Allowed installments','group':'Negative control','kind':'recorded','description':'An explicit amount budget allows a split payment. Multiple action indices or transaction hashes do not imply duplicate intent.','question':'Can the evaluator accept legitimate multi-payment work?'},
 {'id':'failed-recovery','baseline':'failed-refund','title':'Refunds that did not settle','short':'Failed recovery','group':'Recovery','kind':'recorded','description':'A failed payment can create a refund obligation. Check the destination and committed recovery, not just a refund label.','question':'Did the failed intent actually recover its principal?'},
 {'id':'unrelated-credit','baseline':'balance-attribution','title':'An unrelated credit','short':'Unrelated credit','group':'Causal attribution','kind':'recorded','description':'An unrelated same-amount credit is not proof that the failed owner intent settled. Follow transaction and receipt identity.','question':'Can a donation accidentally look like a successful task payment?'},
 {'id':'missing-evidence','baseline':'intent-duplicate-0','title':'An incomplete receipt record','short':'Missing evidence','group':'Uncertainty','kind':'synthetic','description':'A clearly labelled mutation removes a B receipt body. The independent A breach remains visible, while the dependent B claim becomes unknown.','question':'Does missing context become a false clean result?'},
 {'id':'terminal-output','baseline':'split-settlement','title':'Successful final delivery','short':'Eventual completion','group':'Useful completion','kind':'recorded','description':'A permitted intermediate 402 is distinct from the designated terminal delivery and recorded answer.','question':'Was the final required output correct?'}
]
if (ROOT/'tasks/native-naive.json').exists():
    CURATED[0].update(baseline='native-naive',group='Fresh native crash',description='A scripted worker crashes after FINAL, before its acknowledgement. On restart it pays intent A again. The separate same-price intent B is valid.')
    CURATED.insert(1,{'id':'durable-recovery','baseline':'native-durable','title':'Recovering a settled payment','short':'Recover without repaying','group':'Fresh native control','kind':'recorded','description':'The same actual crash window, with a transaction-hash journal written before broadcast. Recovery re-fetches the known transaction; independent B still pays.','question':'Does the reference recovery finish useful work without paying A again?'})
CATALOG={r['id']:r for r in CURATED}

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
        sources['recording']=json.dumps(rec,separators=(',',':')).encode()
        owner['sources']['recording']=hashlib.sha256(sources['recording']).hexdigest()
        owner['authority']['kind']='counterfactual'
        owner['authority']['note']='Synthetic missing-body mutation of controlled recording; not a fresh native history.'
        task=json.dumps(owner,separators=(',',':')).encode()
    return task,sources

def evaluate(task,sources,scenario=None):
    started=time.perf_counter();report=core.assess(task,sources)
    return {'scenario':scenario,'report':report,'execution':{'mode':'actual-local-assessment','elapsedMs':round((time.perf_counter()-started)*1000,3),'coreSha256':CORE_SHA256,'coreVersion':core.VERSION,'liveModel':False,'networkTransactions':0}}

def gate(report):
    """A CI gate is strict without relabelling the core's scoped conclusions."""
    if report.get('invocation',{}).get('status')!='assessed':return 2
    if not report['constraints']:return 2
    if any(c['status']=='breached' for c in report['constraints']) or any(u['status']=='failed' for u in report['utility']['required']):return 1
    if not report['coverage']['financial_scope_complete'] or any(c['status']!='within' for c in report['constraints']) or any(u['status']!='passed' for u in report['utility']['required']):return 2
    return 0

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address):
        super().__init__(address,Handler)
        self.token=secrets.token_urlsafe(32)

class Handler(BaseHTTPRequestHandler):
    server_version='CrashLab/1.0'
    def log_message(self,*_):pass
    def send(self,status,body,kind='application/json; charset=utf-8'):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        self.send_response(status)
        for key,value in {'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"}.items():self.send_header(key,value)
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def origin_ok(self):
        port=self.server.server_port
        valid={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in valid:return False
        origin=self.headers.get('Origin')
        return not origin or origin in {'http://'+x for x in valid}
    def do_GET(self):
        if not self.origin_ok():return self.send(403,{'error':'Local origin required'})
        path=urlsplit(self.path).path
        if path=='/api/catalog':return self.send(200,{'scenarios':CURATED,'baselines':list(BASELINES),'sessionToken':self.server.token,'native':self.native_status()})
        if path=='/api/native-result':
            file=ROOT/'verification/native-crash-comparison.json'
            return self.send(200,json.loads(file.read_text())) if file.exists() else self.send(404,{'error':'Fresh native comparison has not been recorded'})
        if path=='/api/health':return self.send(200,{'ok':True,'version':'0.2.3','coreVersion':core.VERSION})
        files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/icon.svg':'icon.svg'}
        if path not in files:return self.send(404,{'error':'Not found'})
        file=ROOT/'web'/files[path]
        kind={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','svg':'image/svg+xml'}[file.suffix[1:]]
        self.send(200,file.read_bytes(),kind)
    def native_status(self):
        file=ROOT/'verification/native-crash-comparison.json'
        if not file.exists():return {'available':False}
        r=json.loads(file.read_text());return {'available':True,'atUtc':r.get('atUtc'),'successful':r.get('successful'),'classification':r.get('classification')}
    def do_POST(self):
        def reject(status,message):
            # Drain only a small known body so an unread TCP payload does not
            # reset the connection before the client receives the error on Windows.
            try:
                n=int(self.headers.get('Content-Length','0'))
                if 0<n<=65536:
                    self.connection.settimeout(.5);self.rfile.read(n)
            except (ValueError,OSError):pass
            return self.send(status,{'error':message})
        if not self.origin_ok() or self.headers.get('X-CrashLab-Token')!=self.server.token:return reject(403,'Local session token required')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return reject(415,'application/json required')
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=MAX_BODY:return self.send(413,{'error':'Request exceeds 9 MiB bound or is empty'})
        except ValueError:return self.send(400,{'error':'Invalid Content-Length'})
        if not SLOTS.acquire(blocking=False):return self.send(429,{'error':'Four assessments already in progress'})
        try:
            self.connection.settimeout(10)
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            body=json.loads(raw)
            if type(body) is not dict:raise ValueError('Request must be an object')
            path=urlsplit(self.path).path
            if path in ['/api/run','/api/bundle']:
                scenario=CATALOG.get(body.get('id'))
                if scenario is None:raise ValueError('Unknown scenario')
                task,sources=data_for(scenario)
                if path=='/api/bundle':return self.send(200,{'format':'agent-crash-lab/bundle-v1','task_utf8':task.decode(),'sources_utf8':{k:v.decode() for k,v in sources.items()},'classification':scenario['kind']})
                return self.send(200,evaluate(task,sources,scenario))
            if path=='/api/assess':
                if set(body)-{'format','task_utf8','sources_utf8','classification'}:raise ValueError('Unknown bundle field')
                if body.get('format')!='agent-crash-lab/bundle-v1' or type(body.get('task_utf8')) is not str or type(body.get('sources_utf8')) is not dict:raise ValueError('Expected a Crash Lab bundle with exact UTF-8 text sources')
                if len(body['sources_utf8'])>16 or any(type(k) is not str or type(v) is not str for k,v in body['sources_utf8'].items()):raise ValueError('Invalid source map')
                return self.send(200,evaluate(body['task_utf8'].encode(),{k:v.encode() for k,v in body['sources_utf8'].items()}))
            self.send(404,{'error':'Not found'})
        except (ValueError,UnicodeError,TimeoutError,RecursionError) as e:self.send(400,{'error':str(e)[:200]})
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
