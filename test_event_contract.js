'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const source=fs.readFileSync(__dirname+'/web/token.js','utf8'),context=vm.createContext({});vm.runInContext(fs.readFileSync(__dirname+'/web/token-events.js','utf8'),context);vm.runInContext(source.slice(0,source.indexOf('// All imported text')),context);
const script=`import pathlib,runpy,json,copy,hashlib
r=pathlib.Path.cwd();a=runpy.run_path(str(r/'token_review.py'));rows=[]
def add(d,label):
 raw=a['pack'](d);rows.append({'label':label,'input':d,'inputHash':hashlib.sha256(raw).hexdigest(),'report':a['review'](raw)})
for p in sorted((r/'verification/event-study/inputs').glob('*.json')):add(json.loads(p.read_bytes()),p.stem)
base=json.loads((r/'verification/event-study/inputs/malformed-promotion.json').read_bytes())
logrow=base['steps'][0]['transactions'][0]['result']['receipts_outcome'][0]['outcome']
for label,line in [('duplicate-owner','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"alice","owner_id":"bob","amount":"100"}]}'),('escaped-duplicate','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"alice","owner_\\\\u0069d":"bob","amount":"100"}]}'),('float-metadata','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"bob","amount":"100","extra":1.0}]}'),('oversized-integer','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"bob","amount":"100","extra":'+'1'*4301+'}]}'),('valid-big-integer','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"alice","amount":"100","extra":'+'1'*400+'}]}'),('valid-emoji-memo','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"alice","amount":"100","memo":"hi \\U0001f680"}]}'),('surrogate-memo','EVENT_JSON:{"standard":"nep141","version":"1.0.0","event":"ft_mint","data":[{"owner_id":"alice","amount":"100","memo":"\\\\uD800"}]}')]:
 logrow['logs']=[line];add(copy.deepcopy(base),label)
logrow['logs']=['EVENT_JSON:{"standard":"another-standard","extra":true}']
for label,change in [('scope',lambda d:d['scope'].update(closed_intervals=False)),('identity',lambda d:d['asset'].update(deployed_after='changed')),('liability',lambda d:d['steps'][0]['after'].update(liabilities='1')),('height',lambda d:d['steps'][0]['after'].update(block_height=1)),('complete',lambda d:None)]:
 d=copy.deepcopy(base);change(d);add(d,label)
print(json.dumps(rows))`;
const child=spawnSync('python',['-I','-S','-c',script],{cwd:__dirname,encoding:'utf8',maxBuffer:4*1024*1024});assert.equal(child.status,0,child.stderr);const rows=JSON.parse(child.stdout);let accepted=0,rejected=0;
const promote=report=>{const r=structuredClone(report),s=r.steps[0];s.events=[];s.gross_in=s.gross_out=s.event_net=s.transfer_out=s.parity_difference=s.held_delta=s.rights_delta='0';s.rights_debit_without_transfer=s.backing_shortfall='0';s.reasons=[];s.state_event_agreement='agrees';s.ledger_relation='matched';s.backing='sufficient';s.conclusion=r.conclusion='recorded-parity';return r;};
for(const row of rows){
 const check=r=>context.validateTokenReport(r,row.input,row.inputHash,row.report.assessor_sha256);assert.doesNotThrow(()=>check(row.report),row.label);accepted++;
 if(row.report.steps[0].events.length){const r=structuredClone(row.report);r.steps[0].events.pop();assert.throws(()=>check(r),row.label);rejected++;}
 if(row.report.steps[0].reasons.length){assert.throws(()=>check(promote(row.report)),row.label);rejected++;}
 const wrong=structuredClone(row.report);wrong.steps[0].ignored_event_logs++;assert.throws(()=>check(wrong));rejected++;
}
const oldSource=fs.readFileSync(__dirname+'/verification/event-study/frozen-v012-token.js.txt','utf8'),old=vm.createContext({});vm.runInContext(oldSource.slice(0,oldSource.indexOf('// All imported text')),old);let historicalAccepted=0;
for(const id of ['roundtrip-omission','malformed-promotion']){
 const input=JSON.parse(fs.readFileSync(__dirname+'/verification/event-study/inputs/'+id+'.json')),report=JSON.parse(fs.readFileSync(__dirname+'/verification/event-study/initial/'+id+'-counterfeit.json'));
 assert.doesNotThrow(()=>old.validateTokenReport(report,input,report.recording_sha256,report.assessor_sha256));historicalAccepted++;
 const row=rows.find(r=>r.label===id),changed=promote(row.report);assert.throws(()=>context.validateTokenReport(changed,row.input,row.inputHash,row.report.assessor_sha256));rejected++;
}
console.log(JSON.stringify({acceptedReports:accepted,rejectedMutations:rejected,historicalInvalidReportsAccepted:historicalAccepted,officialSerializedVectors:8,meaning:'Source-informed event conformance and full-event response boundary checks; no independent end-to-end accuracy claim'}));
