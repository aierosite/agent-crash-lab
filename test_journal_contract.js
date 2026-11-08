'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),cp=require('node:child_process'),crypto=require('node:crypto');
const {nativeJournalBinding,validateNativeJournalReport,journalJSON}=require('./web/journal-contract.js');
const hash=path=>crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex');
const source=hash('receipt_journal.py'),math=hash('receipt_journal_math.py');
const script=String.raw`from pathlib import Path
import json,runpy
r=Path.cwd();api=runpy.run_path(str(r/'receipt_journal.py'));data=r/'verification/receipt-journal'
rows=[]
for s in json.loads((data/'samples.json').read_bytes()):
 b={'format':'agent-crash-lab/native-journal-bundle-v1','journal_utf8':(r/s['journal']).read_bytes().decode(),'policy_utf8':(r/s['policy']).read_bytes().decode()}
 rows.append({'id':s['id'],'bundle':b,'report':api['assess_bundle'](b['journal_utf8'],b['policy_utf8'])})
for s in json.loads((data/'BOUNDARY-AUDIT.json').read_bytes())['rows']:
 if s['expected']=='reject':continue
 b={'format':'agent-crash-lab/native-journal-bundle-v1','journal_utf8':(data/'controls'/(s['name']+'.jsonl')).read_bytes().decode(),'policy_utf8':(data/'controls'/(s['name']+'.policy.json')).read_bytes().decode()}
 rows.append({'id':s['name'],'bundle':b,'report':api['assess_bundle'](b['journal_utf8'],b['policy_utf8'])})
original=next(row for row in rows if row['id']=='after-principal-refund');b=dict(original['bundle']);events=[json.loads(line) for line in b['journal_utf8'].splitlines()]
def mutate(value):
 if type(value) is list:
  for item in value:mutate(item)
 elif type(value) is dict:
  if set(value)=={'Transfer'} and value['Transfer'].get('deposit')=='100':value['Transfer']['deposit']=100
  for item in value.values():mutate(item)
mutate(events);b['journal_utf8']=''.join(json.dumps(e,separators=(',',':'))+'\n' for e in events)
rows.append({'id':'integer-principal-refund','bundle':b,'report':api['assess_bundle'](b['journal_utf8'],b['policy_utf8'])})
print(json.dumps(rows))`;
const rows=JSON.parse(cp.execFileSync('python',['-I','-S','-c',script],{maxBuffer:16*1024*1024,encoding:'utf8'}));
const raw=b=>new TextEncoder().encode(JSON.stringify(b));
(async()=>{
 const bindings=new Map();for(const row of rows){const binding=await nativeJournalBinding(raw(row.bundle),source,math);bindings.set(row.id,binding);validateNativeJournalReport(row.report,binding);assert.equal(binding.journal_sha256,crypto.createHash('sha256').update(row.bundle.journal_utf8).digest('hex'));assert.equal(binding.policy_sha256,crypto.createHash('sha256').update(row.bundle.policy_utf8).digest('hex'));}
 let rejected=0;const mutate=(id,name,change)=>{const row=rows.find(r=>r.id===id),report=structuredClone(row.report);change(report);assert.throws(()=>validateNativeJournalReport(report,bindings.get(id)),undefined,name);rejected++;};
 mutate('before-payment','pending-is-not-green',r=>{r.assessment.required_payment_gate=0;r.assessment.operation_closed=true;r.assessment.payment_status='settled';r.assessment.principal_received='100';r.assessment.beneficiary_delta='100';r.assessment.pending_receipt_ids=[];});
 mutate('after-payment-before-ack','paid-does-not-complete-transcript',r=>r.assessment.whole_run_complete=true);
 mutate('after-principal-refund','refund-is-not-merchant-delivery',r=>{r.assessment.required_payment_gate=0;r.assessment.payment_status='settled';r.assessment.principal_received='100';r.assessment.beneficiary_delta='100';r.assessment.failed_principal_receipts=[];});
 mutate('failed-payment-refund-pending','refund-not-yet-settled',r=>r.assessment.principal_refunds[0].status='settled');
 mutate('after-principal-refund','known-failure-survives',r=>{r.assessment.failed_principal_receipts=[];r.assessment.required_payment_gate=2;r.assessment.payment_status='unknown';});
 mutate('before-payment-torn-block-result','unknown-amount-is-null',r=>{r.assessment.principal_received='0';r.assessment.principal_committed='0';r.assessment.beneficiary_delta='0';});
 mutate('known-cap-breach-with-incomplete-run','cap-breach-cannot-become-unknown',r=>{r.assessment.violations=[];r.assessment.required_payment_gate=2;});
 mutate('known-wrong-recipient-with-incomplete-run','wrong-recipient-cannot-become-paid',r=>{r.assessment.violations=[];r.assessment.required_payment_gate=0;r.assessment.payment_status='settled';r.assessment.principal_received='100';r.assessment.beneficiary_delta='100';r.assessment.pending_receipt_ids=[];r.assessment.operation_closed=true;});
 mutate('nonempty-internal-queue','internal-queue-cannot-disappear',r=>{r.assessment.internal_queue_remaining=false;r.assessment.operation_closed=true;});
 mutate('missing-queue-measurement','missing-queue-is-not-observed-zero',r=>{r.assessment.queue_observation_missing=false;r.assessment.operation_closed=true;});
 for(const field of ['assessor_sha256','math_sha256','journal_sha256','policy_sha256'])mutate('before-payment','bound-'+field,r=>r[field]='0'.repeat(64));
 for(const field of ['required_payment_gate','complete_records'])mutate('before-payment','bool-'+field,r=>r.assessment[field]=true);
 mutate('after-principal-refund','unknown-field',r=>r.assessment.retry_authorized=true);
 mutate('before-payment','truncated-error',r=>delete r.assessment.pending_receipt_ids);
 mutate('before-payment','scope',r=>r.assessment.scope='Authenticated chain state');
 const report=structuredClone(rows[0].report);let read=false;Object.defineProperty(report,'assessment',{enumerable:true,get(){read=true;throw Error('Getter must not run');}});assert.throws(()=>validateNativeJournalReport(report,bindings.get(rows[0].id)));assert.equal(read,false);rejected++;
 const b=rows[0].bundle;await assert.rejects(nativeJournalBinding(raw({...b,journal_utf8:'\ud800'}),source,math));rejected++;
 await assert.rejects(nativeJournalBinding(raw({...b,policy_utf8:b.policy_utf8.replace('"step": 2','"step": 2, "step": 2')}),source,math));rejected++;
 await assert.rejects(nativeJournalBinding(raw({...b,journal_utf8:' '.repeat(4194305)}),source,math));rejected++;
 assert.equal(journalJSON('{"n":9007199254740993}').n,9007199254740993n);
 for(const text of ['{"x":1,"x":2}','{"x":1.5}','{"x":NaN}','{"x":01}','{"x":true,}','{"x":"\\ud800"}'])assert.throws(()=>journalJSON(text));
 console.log(JSON.stringify({acceptedCompleteReports:rows.length,rejectedControls:rejected,integers:'Exact BigInt projection, never rounded through Number',scope:'Same-author native receipt/payment projection and exact-byte response binding; no independent conservation, authenticity or runtime execution.'}));
})().catch(error=>{console.error(error);process.exitCode=1;});
