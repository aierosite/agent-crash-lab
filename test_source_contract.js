'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process'),{webcrypto}=require('node:crypto');
const source=fs.readFileSync(__dirname+'/web/token.js','utf8'),context=vm.createContext({crypto:webcrypto,TextEncoder});vm.runInContext(fs.readFileSync(__dirname+'/web/token-events.js','utf8'),context);vm.runInContext(source.slice(0,source.indexOf('// All imported text')),context);
const script=`import pathlib,runpy,json,hashlib
r=pathlib.Path.cwd();app=runpy.run_path(str(r/'workbench.py'));review=runpy.run_path(str(r/'token_ledger.py'))['review'];c=json.loads((r/'web/catalog.json').read_bytes());s=c['sourceCorroboration'];meta={**s,'verifierSha256':c['files'][s['module']]['sha256']};rows=[]
for row in s['cases']:
 raw=(r/'verification/token-study'/(row['id']+'.json')).read_bytes();rows.append({'review':review(raw),'value':app['token_source_check']({'recording_sha256':hashlib.sha256(raw).hexdigest()})})
print(json.dumps({'meta':meta,'cases':rows}))`;
const child=spawnSync('python',['-I','-S','-c',script],{cwd:__dirname,encoding:'utf8',maxBuffer:2*1024*1024});assert.equal(child.status,0,child.stderr);const data=JSON.parse(child.stdout);
const reverse=v=>Array.isArray(v)?v.map(reverse):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).reverse().map(k=>[k,reverse(v[k])])):v;
(async()=>{let accepted=0,rejected=0;
 for(const row of data.cases){
  const check=(value,review=row.review,meta=data.meta)=>context.validateSourceCheck(value,review,meta);await assert.doesNotReject(()=>check(row.value));accepted++;await assert.doesNotReject(()=>check(reverse(row.value)));accepted++;
  const mutations=[v=>{v.recordingSha256='0'.repeat(64);},v=>{v.datasetSha256='0'.repeat(64);},v=>{v.verifierSha256='0'.repeat(64);},v=>{v.signatureOrStateProofVerified=true;},v=>{v.independentGrading=true;},v=>{v.replayNetworkCalls=1;},v=>{v.corroboration.operationReference.rootSucceeded=false;},v=>{v.corroboration.operationReference.status=v.corroboration.operationReference.status==='passed'?'failed':'passed';},v=>{v.corroboration.operationReference.expectedRightsAfter=v.corroboration.operationReference.observedRightsAfter==='900'?'901':'6000000';},v=>{v.corroboration.operationReference.payout.recipient='wrong.testnet';},v=>{v.corroboration.points[0].fields.credit='1';},v=>{v.corroboration.points[0].rightsProofs.credit.byteOffset++;},v=>{v.corroboration.points[0].rawQueries[0].responseSha256='0'.repeat(64);},v=>{v.corroboration.receiptDetailsCapture='../wrong';},v=>{v.corroboration.points.pop();}];
  for(const change of mutations){const value=structuredClone(row.value);change(value);await assert.rejects(()=>check(value));rejected++;}
  const changed=structuredClone(row.review);changed.recording_sha256='0'.repeat(64);await assert.rejects(()=>check(row.value,changed));rejected++;
  const meta=structuredClone(data.meta);meta.cases.find(c=>c.recordingSha256===row.review.recording_sha256).expectedResponseSha256='0'.repeat(64);await assert.rejects(()=>check(row.value,row.review,meta));rejected++;
 }
 console.log(JSON.stringify({acceptedSealedResponses:accepted,rejectedMutations:rejected,meaning:'Exact-recording and full nested response integrity for a sealed replay; not external grading or source authentication'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
