"""Optional Linux-only, owned NEAR sandbox crash/restart experiment.

Not a live-model benchmark or production payment protocol. Uses ephemeral keys
for a fresh isolated genesis and only 127.0.0.1 RPC. No existing account access.
Codec follows nearcore 2.14.0 / bc4e9e8cfb03d9e82f027883055624e18576993e.
cryptography is optional and required ONLY by this runner, not the product core.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,base64,hashlib,json,os,signal,socket,struct,subprocess,sys,tempfile,time,urllib.request,uuid

PIN='797b9d7a9a23907048d68a427e86a55c94f1de232dbfb8b8a1eec09ecef3bf13'
ALPHABET='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
def b58(raw):
    n=int.from_bytes(raw,'big');s=''
    while n:n,r=divmod(n,58);s=ALPHABET[r]+s
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+s
def un58(s):
    n=0
    for c in s:n=n*58+ALPHABET.index(c)
    return b'\0'*(len(s)-len(s.lstrip('1')))+(n.to_bytes((n.bit_length()+7)//8,'big') if n else b'')
def text(s):
    b=s.encode();return struct.pack('<I',len(b))+b
def emit(o):print(json.dumps(o,separators=(',',':')),flush=True)

def worker():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    c=json.load(sys.stdin);counter=0
    def rpc(method,params):
        nonlocal counter
        counter+=1;request={'jsonrpc':'2.0','id':c['invocation']+'-'+str(counter),'method':method,'params':params}
        with urllib.request.urlopen(urllib.request.Request(c['endpoint'],data=json.dumps(request).encode(),headers={'Content-Type':'application/json'}),timeout=10) as r:response=json.load(r)
        emit({'type':'rpc','record':{'request':request,'response':response}})
        if 'error' in response:raise ValueError('Local RPC error')
        return response['result']
    journal=Path(c['journal']);record=json.loads(journal.read_text()) if journal.exists() else {}
    intent=c['intent'];recovered=c['policy']=='durable' and intent in record
    if recovered:
        txhash=record[intent]['tx_hash']
        expanded=rpc('tx_status',{'tx_hash':txhash,'sender_account_id':c['owner'],'wait_until':'FINAL'})
    else:
        current=rpc('query',{'request_type':'view_access_key','finality':'final','account_id':c['owner'],'public_key':c['public']})
        public=un58(c['public'].split(':')[1]);amount=int(c['amount'])
        tx=text(c['owner'])+b'\0'+public+(current['nonce']+1).to_bytes(8,'little')+text(c['merchant'])+un58(current['block_hash'])+struct.pack('<I',1)+b'\x03'+amount.to_bytes(16,'little')
        digest=hashlib.sha256(tx).digest();txhash=b58(digest)
        signed=tx+b'\0'+Ed25519PrivateKey.from_private_bytes(bytes.fromhex(c['seed'])).sign(digest)
        if c['policy']=='durable':
            record[intent]={'tx_hash':txhash,'phase':'prepared-before-send'}
            temporary=journal.with_suffix('.tmp')
            with temporary.open('w') as f:json.dump(record,f);f.flush();os.fsync(f.fileno())
            os.replace(temporary,journal)
        rpc('send_tx',{'signed_tx_base64':base64.b64encode(signed).decode(),'wait_until':'FINAL'})
        if c['crash']:
            emit({'type':'crash','after':'send_tx returned FINAL','before':'application acknowledgement / useful output','tx_hash':txhash})
            os._exit(77)
        expanded=rpc('tx_status',{'tx_hash':txhash,'sender_account_id':c['owner'],'wait_until':'FINAL'})
    if expanded.get('final_execution_status')!='FINAL':raise ValueError('Recovery is not final')
    emit({'type':'ack','intent':intent,'tx_hash':txhash,'recoveredWithoutNewSend':recovered})

def experiment(binary,output,live=None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat,PrivateFormat,NoEncryption
    if sys.platform!='linux':raise ValueError('Run optional native experiment in Linux / WSL')
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=PIN:raise ValueError('Expected pinned official sandbox2.14binary; no unverified executable is run')
    output.mkdir(parents=True,exist_ok=True)
    cap=10**23;temporary=tempfile.TemporaryDirectory(prefix='acl-owned-native-');root=Path(temporary.name);os.chmod(root,0o700)
    key=Ed25519PrivateKey.generate();pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw);seed=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()).hex()
    public='ed25519:'+b58(pub);owner='owner.crashlab.near';merchant='merchant.crashlab.near'
    expected_doc=lambda i:{'resource':'inventory-snapshot','version':'v1','invoice':i,'source':'owned-local-merchant','rows':[{'sku':'A01','available':7,'forecast':21},{'sku':'B02','available':11,'forecast':10},{'sku':'C03','available':2,'forecast':19}]}
    precommit={'atUtc':datetime.now(timezone.utc).isoformat(),'mode':'owned-local-only','cap':str(cap),'expectedAnswer':{'sku':'C03','units':17},'expectedDocuments':{i:expected_doc(i) for i in ['A','B']},'expectedPolicies':{'naive':{'A':str(2*cap),'B':str(cap)},'durable':{'A':str(cap),'B':str(cap)}},'fault':'Actual worker process exit77 after FINAL before ack','limitations':'Known-family source-informed integration exercise, same operator; scripted workers, not live-model or independent holdout; precommit is written before executing trials'}
    if live is not None:
        precommit=live.plan
    (output/'native-precommit.json').write_text(json.dumps(precommit,indent=2))
    env=os.environ.copy();env.update(RUST_LOG='error',RAYON_NUM_THREADS='2')
    combined=[];all_stopped=True
    policies=['naive','durable'] if live is None else precommit['policies']
    for policy in policies:
        home=root/policy;home.mkdir(mode=0o700);node=None;log=None;records=[];seq=0
        run={'policy':policy,'rpcObservations':records,'utilityObservations':[],'workers':[],'mainnetOrTestnetRequests':0,'privateKeysExported':False}
        def rpc(method,params):
            nonlocal seq
            seq+=1;req={'jsonrpc':'2.0','id':policy+'-observer-'+str(seq),'method':method,'params':params}
            with urllib.request.urlopen(urllib.request.Request(endpoint,data=json.dumps(req).encode(),headers={'Content-Type':'application/json'}),timeout=10) as r:res=json.load(r)
            records.append({'request':req,'response':res})
            if 'error' in res:raise ValueError('Observer local RPC error')
            return res['result']
        try:
            init=subprocess.run([str(binary),'--home',str(home),'init','--fast'],capture_output=True,env=env,timeout=20)
            if init.returncode:raise ValueError('Sandbox init failed')
            cp=home/'config.json';config=json.loads(cp.read_text());config.setdefault('network',{})['boot_nodes']='';config['network']['trusted_stun_servers']=[];config.setdefault('telemetry',{})['endpoints']=[];config.setdefault('store',{})['max_open_files']=3000;cp.write_text(json.dumps(config))
            gp=home/'genesis.json';genesis=json.loads(gp.read_text())
            for account,balance in [(owner,100*10**24),(merchant,10*10**24)]:
                genesis['records'].append({'Account':{'account_id':account,'account':{'amount':str(balance),'locked':'0','code_hash':'11111111111111111111111111111111','storage_usage':182}}});genesis['total_supply']=str(int(genesis['total_supply'])+balance)
            genesis['records'].append({'AccessKey':{'account_id':owner,'public_key':public,'access_key':{'nonce':0,'permission':'FullAccess'}}});gp.write_text(json.dumps(genesis))
            ports=[]
            for _ in range(2):
                with socket.socket() as s:s.bind(('127.0.0.1',0));ports.append(s.getsockname()[1])
            endpoint='http://127.0.0.1:'+str(ports[0]);log=(home/'node.log').open('wb')
            node=subprocess.Popen([str(binary),'--home',str(home),'run','--rpc-addr','127.0.0.1:'+str(ports[0]),'--network-addr','127.0.0.1:'+str(ports[1])],stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env,start_new_session=True)
            deadline=time.monotonic()+25;status=None
            while time.monotonic()<deadline:
                if node.poll() is not None:raise ValueError('Owned node exited during startup')
                try:
                    with urllib.request.urlopen(endpoint+'/status',timeout=2) as r:status=json.load(r)
                    if status.get('sync_info',{}).get('latest_block_height',0)>=5:break
                except (OSError,ValueError):pass
                time.sleep(.15)
            if not status or status.get('chain_id')!=genesis['chain_id'] or status.get('sync_info',{}).get('latest_block_height',0)<5:raise ValueError('Fresh owned chain not ready')
            run.update(chainId=status['chain_id'],protocolVersion=status['protocol_version'],startedAtUtc=datetime.now(timezone.utc).isoformat())
            before=rpc('query',{'request_type':'view_account','finality':'final','account_id':merchant})
            sends=[]
            account_query={'request_type':'view_account','finality':'final','account_id':merchant}
            steps=[('A',True),('A',False),('B',False)]
            if live is not None:
                steps=live.plan['steps']
                run['balanceCheckpoints']=[len(records)-1]
            for intent,crash in steps:
                attempt={'intent':intent,'crashRequested':crash,'exitCode':None,'events':[]}
                run['workers'].append(attempt)
                amount=cap
                admitted=True
                if live is not None:
                    admitted,amount,trace=live.decide(intent)
                    attempt.update(admitted=admitted,decision=trace,quotedPrincipal=str(amount))
                if admitted:
                    cfg={'invocation':policy+'-'+str(len(run['workers'])-1),'endpoint':endpoint,'journal':str(home/'journal.json'),'policy':policy,'owner':owner,'merchant':merchant,'public':public,'seed':seed,'amount':str(amount),'intent':intent,'crash':crash}
                    proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],input=json.dumps(cfg).encode(),capture_output=True,timeout=25)
                    attempt['exitCode']=proc.returncode
                    attempt['events']=[json.loads(line) for line in proc.stdout.splitlines() if line]
                    if proc.returncode!=(77 if crash else 0):
                        raise ValueError(f'Owned worker failed in {policy}/{intent} (exit {proc.returncode})')
                events=attempt['events']
                for event in events:
                    if event['type']=='rpc':
                        idx=len(records);records.append(event['record'])
                        if event['record']['request']['method']=='send_tx':
                            txhash=event['record']['response']['result']['transaction']['hash'];sends.append({'index':idx,'intent':intent,'hash':txhash})
                if live is not None:
                    rpc('query',account_query)
                    run['balanceCheckpoints'].append(len(records)-1)
                if not crash and admitted:
                    # Actual controlled merchant HTTP delivery follows the recovered payment.
                    from http.server import BaseHTTPRequestHandler,HTTPServer
                    import threading
                    document=expected_doc(intent) if live is None else live.plan['deliveries'][intent]
                    class Merchant(BaseHTTPRequestHandler):
                        def do_GET(self):
                            data=json.dumps(document).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                        def log_message(self,*_):pass
                    service=HTTPServer(('127.0.0.1',0),Merchant);thread=threading.Thread(target=service.handle_request);thread.start()
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:'+str(service.server_port)+'/inventory',timeout=5) as response:body=response.read().decode();httpstatus=response.status
                    finally:thread.join(timeout=5);service.server_close()
                    obs={'invoice':intent,'requestedVersion':'v1','httpStatus':httpstatus,'responseUtf8':body}
                    if live is None:
                        received=json.loads(body);answer=max(received['rows'],key=lambda row:max(0,row['forecast']-row['available']));obs['scriptedAnswer']={'sku':answer['sku'],'units':max(0,answer['forecast']-answer['available'])}
                    else:
                        obs['recordedAnswer'],obs['inference']=live.answer(body)
                    run['utilityObservations'].append(obs)
                elif live is not None and not crash and intent in live.plan['expectedDocuments']:
                    run['utilityObservations'].append({'invoice':intent,'requestedVersion':'v1','reason':'payment_not_admitted'})
            # Independent observer expands ALL hashes, including the crashed worker's first send.
            for send in sends:rpc('tx_status',{'tx_hash':send['hash'],'sender_account_id':owner,'wait_until':'FINAL'})
            after=rpc('query',{'request_type':'view_account','finality':'final','account_id':merchant})
            run.update(sends=sends,merchantBefore=before,merchantAfter=after,merchantBalanceIncrease=str(int(after['amount'])-int(before['amount'])),expectedMerchantIncrease=str((3 if policy=='naive' else 2)*cap))
            if live is None:
                assert run['merchantBalanceIncrease']==run['expectedMerchantIncrease']
            else:
                del run['expectedMerchantIncrease']
        finally:
            if node is not None:
                if node.poll() is None:
                    os.killpg(node.pid,signal.SIGTERM)
                    try:node.wait(timeout=6)
                    except subprocess.TimeoutExpired:os.killpg(node.pid,signal.SIGKILL);node.wait(timeout=3)
                run['ownedNodeStopped']=node.poll() is not None;all_stopped=all_stopped and run['ownedNodeStopped']
            if log:log.close()
        combined.append(run)
    evidence={'atUtc':datetime.now(timezone.utc).isoformat(),'classification':'Actual source-informed local native crash/restart integration with scripted workers; not a live model or external holdout','sandboxSha256':PIN,'owner':owner,'merchant':merchant,'runs':combined,'ownedNodeStopped':all_stopped,'nativeSendAttempts':sum(len(r['sends']) for r in combined),'privateKeysExported':False,'temporaryOwnedHome':str(root)}
    if live is not None:
        evidence['classification']='Live local model decisions and answers with actual owned sandbox transfers and process fault injection'
    (output/'native-observation.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps({'successful':True,'ownedNodeStopped':all_stopped,'nativeSendAttempts':evidence['nativeSendAttempts'],'output':str(output)}))
    temporary.cleanup()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',action='store_true');p.add_argument('--binary',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.worker:return worker()
    if not a.binary or not a.output:p.error('--binary and --output required')
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Native experiment deadline')));signal.alarm(150)
    try:experiment(a.binary.resolve(),a.output.resolve())
    finally:signal.alarm(0)
if __name__=='__main__':main()
