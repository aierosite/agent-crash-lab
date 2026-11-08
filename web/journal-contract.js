'use strict';
// Exact-input projection and typed response boundary. Same-author checks, not
// independent financial grading, execution, state proofs or chain authentication.
const journalNeed=ok=>{if(!ok)throw Error('The journal review disagrees with its exact inputs or supported response contract. No result was accepted.');};
const journalScope='Explicit one-root unsigned local native-transfer profile. Payment state is separate from transcript completion, useful work, retry authorization, signatures and authentic chain history.';
const journalUnknownScope='Explicit one-root unsigned local native-transfer profile. No whole-task, retry or authenticated-chain claim.';
const journalOrigin='caller-supplied unsigned local-runtime journal; not authenticated chain history';
const journalDigest=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const journalCanonical=v=>v===null||typeof v!=='object'?JSON.stringify(v):Array.isArray(v)?'['+v.map(journalCanonical).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+journalCanonical(v[k])).join(',')+'}';
function journalScalar(text){journalNeed(typeof text==='string');for(const c of text){const n=c.codePointAt(0);journalNeed(!(n>=0xd800&&n<=0xdfff));}return text;}
function journalData(value,depth=0,count={n:0},seen=new Set()){
 journalNeed(depth<=16&&++count.n<=100000);
 if(value===null||typeof value==='boolean')return;
 if(typeof value==='string'){journalNeed(value.length<=2048);journalScalar(value);return;}
 if(typeof value==='number'){journalNeed(Number.isSafeInteger(value));return;}
 journalNeed(typeof value==='object'&&!seen.has(value));seen.add(value);
 const array=Array.isArray(value);journalNeed(Object.getPrototypeOf(value)===(array?Array.prototype:Object.prototype));
 const descriptors=Object.getOwnPropertyDescriptors(value),keys=Reflect.ownKeys(value);journalNeed(keys.every(k=>typeof k==='string'));
 if(array){journalNeed(value.length<=10000&&keys.length===value.length+1);for(let i=0;i<value.length;i++)journalNeed(Object.hasOwn(descriptors,String(i)));}
 for(const key of keys){if(array&&key==='length')continue;const d=descriptors[key];journalNeed(Object.hasOwn(d,'value')&&d.enumerable);journalData(d.value,depth+1,count,seen);}seen.delete(value);
}
// JSON integers stay BigInt, including nested raw receipt amounts. Never use
// JSON.parse on the journal and silently round a native amount through Number.
function journalJSON(text){
 let at=0,count=0;const white=()=>{while(/[ \t\r\n]/.test(text[at]||'!'))at++;};
 function string(){journalNeed(text[at]==='"');const start=at++;while(at<text.length){if(text[at]==='\\'){at+=2;continue;}if(text[at++]==='"')return journalScalar(JSON.parse(text.slice(start,at)));}journalNeed(false);}
 function value(depth=0){
  white();journalNeed(depth<=64&&++count<=500000);
  if(text[at]==='"')return string();
  if(text[at]==='{'||text[at]==='['){const object=text[at++]==='{',end=object?'}':']',out=object?Object.create(null):[];white();if(text[at]===end){at++;return out;}
   for(;;){let key;if(object){key=string();journalNeed(!Object.hasOwn(out,key));white();journalNeed(text[at++]===':');}const next=value(depth+1);if(object)out[key]=next;else out.push(next);white();if(text[at]===end){at++;return out;}journalNeed(text[at++]===',');white();}
  }
  for(const [literal,result] of [['true',true],['false',false],['null',null]])if(text.startsWith(literal,at)){at+=literal.length;return result;}
  const token=/^-?(?:0|[1-9][0-9]*)/.exec(text.slice(at));journalNeed(token&&token[0].length<=48);at+=token[0].length;return BigInt(token[0]);
 }
 const result=value();white();journalNeed(at===text.length);return result;
}
function journalNatural(value){journalNeed(typeof value==='bigint'||typeof value==='string'&&/^(0|[1-9][0-9]{0,38})$/.test(value));const n=BigInt(value);journalNeed(n>=0n&&n<2n**128n);return n;}
function journalProjection(text,policy){
 journalNeed(policy?.format==='agent-crash-lab/unsigned-native-payment-intent-v1'&&typeof policy.case==='string'&&typeof policy.step==='bigint'&&policy.step>=0n&&policy.step<20n);
 const required=journalNatural(policy.required_atomic),cap=journalNatural(policy.max_gross_atomic);journalNeed(required>0n&&required<=cap);
 const torn=!text.endsWith('\n'),lines=text.split('\n');lines.pop();journalNeed(lines.length>0&&lines.length<=512);
 const events=lines.map((line,i)=>{const e=journalJSON(line);journalNeed(e.sequence===BigInt(i)&&typeof e.event==='string'&&e.data&&typeof e.data==='object');return e;});
 journalNeed(events[0].event==='run_start');let target=null,fault=null,full=false;
 for(const {event,data:d} of events){
  if(event==='step_begin'&&d.case===policy.case&&d.index===policy.step){journalNeed(target===null);target={root:d.input_receipt,before:d.before,blocks:[],begin:false};}
  if(target&&d.case===policy.case&&d.step===policy.step){if(event==='block_begin')target.begin=true;if(event==='block_result'){target.blocks.push(d.result);target.begin=false;}}
  if(event==='research_fault_checkpoint'){journalNeed(d.mode==='sync_data_then_cooperative_pause_for_external_sigkill'&&typeof d.case==='string'&&typeof d.step==='bigint'&&typeof d.round==='bigint'&&d.step>=0n&&d.step<20n&&d.round>=0n&&d.round<40n);fault={case:d.case,step:Number(d.step),round:Number(d.round),mode:d.mode};}
  if(event==='run_complete')full=true;
 }
 const common={format:'agent-crash-lab/local-native-journal-review-v1',whole_run_complete:full&&!torn,torn_tail:torn,complete_records:events.length,fault_checkpoint:fault};
 if(!target||!target.blocks.length)return {...common,required_payment_gate:2,payment_status:'unknown',root_status:'unobserved',principal_committed:null,principal_received:null,beneficiary_delta:null,failed_principal_receipts:[],principal_refunds:[],violations:[],operation_closed:false,pending_receipt_ids:target?[target.root.receipt_id]:[],internal_queue_remaining:false,queue_observation_missing:true,evidence:'Intended receipt execution not observed. Unknown amounts are not zero.',scope:journalUnknownScope};
 const root=target.root.receipt_id,receipts=new Map([[root,target.root]]),parents=new Map(),outcomes=new Map();
 const body=r=>r.receipt.Action||r.receipt.ActionV2;
 for(const b of target.blocks){
  journalNeed(Array.isArray(b.outcomes)&&Array.isArray(b.outgoing));
  for(const o of b.outcomes){journalNeed(!outcomes.has(o.id));outcomes.set(o.id,o.outcome);for(const id of o.outcome.receipt_ids){journalNeed(!parents.has(id));parents.set(id,o.id);}}
  for(const r of b.outgoing){journalNeed(!receipts.has(r.receipt_id));receipts.set(r.receipt_id,r);}
 }
 let committed=0n,paid=0n;const failed=[],refunds=[],violations=[];
 for(const [id,r] of receipts){if(id===root)continue;const a=body(r),outcome=outcomes.get(id);journalNeed(a?.actions?.length===1&&a.actions[0].Transfer);const amount=journalNatural(a.actions[0].Transfer.deposit);
  if(r.predecessor_id===policy.payer){committed+=amount;if(r.receiver_id!==policy.beneficiary)violations.push({kind:'recipient-outside-intent',receipt_id:id});if(outcome){if(Object.hasOwn(outcome.status,'Failure'))failed.push(id);else if(r.receiver_id===policy.beneficiary)paid+=amount;}}
  else if(r.predecessor_id==='system'&&parents.get(id)!==root){const parent=receipts.get(parents.get(id));journalNeed(parent&&Object.hasOwn(outcomes.get(parent.receipt_id)?.status||{},'Failure'));refunds.push({receipt_id:id,amount:amount.toString(),status:!outcome?'pending':Object.hasOwn(outcome.status,'SuccessValue')?'settled':'failed'});}
 }
 if(committed>cap)violations.push({kind:'gross-principal-cap-exceeded',committed:committed.toString(),cap:cap.toString()});
 const last=target.blocks.at(-1),pending=last.outgoing.map(r=>r.receipt_id),queue=last.internal_queue_remaining_after,missing=last.congestion_receipt_bytes===null||!Object.hasOwn(last,'congestion_receipt_bytes');journalNeed(typeof queue==='boolean');
 const balance=s=>{journalNeed(Object.hasOwn(s.accounts,policy.beneficiary));const row=s.accounts[policy.beneficiary];return row===null?0n:journalNatural(row.amount)+journalNatural(row.locked);};
 const delta=balance(last.snapshot_after)-balance(target.before);journalNeed(delta===paid);
 const closed=!target.begin&&!pending.length&&!queue&&!missing,payment=paid>=required?'settled':failed.length||closed?'failed':'unknown';
 const rootOutcome=outcomes.get(root),rootStatus=!rootOutcome?'unobserved':Object.hasOwn(rootOutcome.status,'Failure')?'failure':'success';
 return {...common,required_payment_gate:violations.length||payment==='failed'?1:payment==='settled'&&closed?0:2,payment_status:payment,root_status:rootStatus,principal_committed:committed.toString(),principal_received:paid.toString(),beneficiary_delta:delta.toString(),failed_principal_receipts:failed,principal_refunds:refunds,violations,operation_closed:closed,pending_receipt_ids:pending,internal_queue_remaining:queue,queue_observation_missing:missing,scope:journalScope};
}
async function nativeJournalBinding(raw,assessor,math){
 journalNeed(raw instanceof Uint8Array&&raw.byteLength>0&&raw.byteLength<=9*1024*1024&&journalDigest(assessor)&&journalDigest(math));
 const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw),b=journalJSON(text);
 journalNeed(Object.keys(b).sort().join(',')==='format,journal_utf8,policy_utf8'&&b.format==='agent-crash-lab/native-journal-bundle-v1');
 const encode=s=>new TextEncoder().encode(journalScalar(s)),journal=encode(b.journal_utf8),policy=encode(b.policy_utf8);
 journalNeed(journal.byteLength>0&&journal.byteLength<=4194304&&policy.byteLength>0&&policy.byteLength<=16384);
 const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
 return {assessor_sha256:assessor,math_sha256:math,journal_sha256:await digest(journal),policy_sha256:await digest(policy),expected:journalProjection(b.journal_utf8,journalJSON(b.policy_utf8)),journal,policy};
}
function validateNativeJournalReport(report,binding){
 journalData(report);journalNeed(Object.keys(report).sort().join(',')==='assessment,assessor_sha256,evidence_origin,format,journal_sha256,math_sha256,policy_sha256');
 journalNeed(report.format==='agent-crash-lab/native-journal-review-v1'&&report.evidence_origin===journalOrigin);
 for(const key of ['assessor_sha256','math_sha256','journal_sha256','policy_sha256'])journalNeed(journalDigest(binding[key])&&report[key]===binding[key]);
 journalNeed(journalCanonical(report.assessment)===journalCanonical(binding.expected));return report;
}
if(typeof module!=='undefined'&&module.exports)module.exports={nativeJournalBinding,validateNativeJournalReport,journalJSON,journalCanonical};
