'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=__dirname,source=fs.readFileSync(root+'/web/token.js','utf8');
const context=vm.createContext({});vm.runInContext(source.slice(0,source.indexOf('// All imported text')),context);const validate=context.validateTokenReport;
const script=`import runpy,pathlib,json,copy,hashlib
r=pathlib.Path.cwd();a=runpy.run_path(str(r/'token_review.py'));out=[]
for p in sorted((r/'verification/token-study').glob('*.json')):
 if p.stem in ['plan','reference','registration']:continue
 raw=p.read_bytes();d=json.loads(raw);out.append({'input':d,'inputHash':hashlib.sha256(raw).hexdigest(),'report':a['review'](raw)})
d=copy.deepcopy(out[0]['input']);d['source']['kind']='synthetic-control';d['id']='partial-control';d['steps'][-1]['transactions'][0]['result']['receipts_outcome'].pop();raw=a['pack'](d);out.append({'input':d,'inputHash':hashlib.sha256(raw).hexdigest(),'report':a['review'](raw)})
t=runpy.run_path(str(r/'test_token_review.py'))['TokenReview']()
for name,held,rights,events in [('capital-topup',(100,200),(100,100),[('ft_transfer','donor','vault',100)]),('payout-and-topup',(100,100),(100,0),[('ft_transfer','vault','owner',100),('ft_transfer','donor','vault',100)]),('assign-surplus',(200,200),(100,200),[])]:
 d=t.episode(name,held,rights,events);raw=a['pack'](d);out.append({'input':d,'inputHash':hashlib.sha256(raw).hexdigest(),'report':a['review'](raw)})
print(json.dumps(out))`;
const child=spawnSync('python',['-I','-S','-c',script],{cwd:root,encoding:'utf8',maxBuffer:4*1024*1024});assert.equal(child.status,0,child.stderr);const cases=JSON.parse(child.stdout);let rejected=0;
for(const row of cases){
 const check=r=>validate(r,row.input,row.inputHash,row.report.assessor_sha256);assert.doesNotThrow(()=>check(row.report));
 const mutations=[r=>{r.format='agent-crash-lab/report-v1';},r=>{r.assessor_sha256='0'.repeat(64);},r=>{r.recording_sha256='0'.repeat(64);},r=>{r.steps.pop();},r=>{r.conclusion='safe';},r=>{r.steps[0].rights_delta='1.5';},r=>{r.steps[0].gross_out=0;},r=>{r.steps[0].before.held='1';},r=>{r.steps[0].transaction_ids=[];},r=>{r.steps[0].rights_debit_without_transfer='1';},r=>{r.new_transactions=1;},r=>{r.asset.contract='foreign.testnet';}];
 const eventStep=row.report.steps.findIndex(s=>s.events.length);
 if(eventStep>=0)mutations.push(r=>{r.steps[eventStep].events[0].executor_id='forged.testnet';},r=>{r.steps[eventStep].events[0].amount='1';},r=>{r.steps[eventStep].events[0].source_pointer='/wrong';},r=>{r.steps[eventStep].events.push(structuredClone(r.steps[eventStep].events[0]));});
 for(const change of mutations){const r=structuredClone(row.report);change(r);assert.throws(()=>check(r));rejected++;}
 if(row.input.id==='partial-control'){
  const r=structuredClone(row.report),s=r.steps.at(-1);s.reasons=[];s.state_event_agreement='agrees';s.ledger_relation='matched';s.rights_debit_without_transfer='0';s.backing_shortfall='0';s.backing='sufficient';s.conclusion='recorded-parity';r.conclusion='recorded-parity';assert.throws(()=>check(r));rejected++;
 }
}
console.log(JSON.stringify({acceptedReports:cases.length,rejectedMutations:rejected,meaning:'Boundary regressions, not an independent financial oracle'}));
