'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const source=fs.readFileSync(__dirname+'/web/token.js','utf8'),ctx=vm.createContext({});
vm.runInContext(fs.readFileSync(__dirname+'/web/token-events.js','utf8'),ctx);vm.runInContext(source.slice(0,source.indexOf('// All imported text')),ctx);
const python=`from pathlib import Path
import json,runpy,hashlib
p=Path.cwd();a=runpy.run_path(str(p/'token_ledger.py'));rows=[]
for c in json.loads((p/'verification/token-ledger-study/cases.json').read_bytes()):
 raw=a['pack'](c['input']);rows.append({'case':c['id'],'input':c['input'],'inputHash':hashlib.sha256(raw).hexdigest(),'report':a['review'](raw)})
print(json.dumps(rows))`;
const child=spawnSync('python',['-I','-S','-c',python],{cwd:__dirname,encoding:'utf8',maxBuffer:4*1024*1024});assert.equal(child.status,0,child.stderr);
const cases=JSON.parse(child.stdout);assert.equal(cases.length,8);let rejected=0;
for(const row of cases){
 const check=r=>ctx.validateTokenReport(r,row.input,row.inputHash,row.report.assessor_sha256,row.report.base_assessor_sha256);assert.doesNotThrow(()=>check(row.report));
 for(const change of [s=>delete s.reported_ledger,s=>{s.reported_ledger=null;},s=>{s.reported_ledger.status='safe';},s=>{s.reported_ledger.before_difference='1';},s=>{s.reported_ledger.after_difference='-0';},s=>{s.reported_ledger.after_difference=3;},s=>{s.reported_ledger.extra=true;},s=>{s.reported_ledger.status=s.reported_ledger.status==='matches'?'conflict':'matches';}]){
  const r=structuredClone(row.report);change(r.steps[0]);assert.throws(()=>check(r));rejected++;
 }
 const legacy=structuredClone(row.report);legacy.format='agent-crash-lab/token-review-v2';delete legacy.steps[0].reported_ledger;assert.throws(()=>check(legacy));rejected++;
 const forgedBase=structuredClone(row.report);forgedBase.base_assessor_sha256='0'.repeat(64);assert.throws(()=>check(forgedBase));rejected++;
 const misleading=structuredClone(row.report);misleading.steps[0].reasons=['The customer payment is confirmed.'];assert.throws(()=>check(misleading));rejected++;
}
console.log(JSON.stringify({registeredReportsAccepted:cases.length,nestedDiagnosticTamperingRejected:rejected,meaning:'Exact-input response boundary controls, not independent financial accuracy'}));
