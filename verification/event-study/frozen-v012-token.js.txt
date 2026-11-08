'use strict';
function validateTokenReport(r,input,inputHash,assessorHash){
 const fail=()=>{throw Error('The review response is incomplete or disagrees with this recording. Retry the review; no result has been accepted.');};
 const keys=(o,list)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join('|')===list.split(' ').sort().join('|');
 const equal=(a,b)=>{if(a===b)return true;if(!a||!b||typeof a!=='object'||typeof b!=='object')return false;const ka=Object.keys(a).sort(),kb=Object.keys(b).sort();return ka.length===kb.length&&ka.every((k,i)=>k===kb[i]&&equal(a[k],b[k]));};
 const integer=x=>typeof x==='string'&&/^-?(0|[1-9]\d{0,48})$/.test(x)&&x!=='-0'&&BigInt(x)>-(2n**160n)&&BigInt(x)<2n**160n;
 const unsigned=x=>integer(x)&&!x.startsWith('-');
 const state=x=>['recorded-parity','recorded-gap','recorded-evidence-conflict','inconclusive'].includes(x);
 const completeCapture=step=>{
  if(!step.transactions.length)return false;
  for(const {result:t} of step.transactions){
   if(t.final_execution_status!=='FINAL'||!['SuccessValue','Failure'].includes(Object.keys(t.status)[0]))return false;
   const rows=[t.transaction_outcome,...t.receipts_outcome],nodes=new Map(rows.map(n=>[n.id,n]));if(nodes.size!==rows.length)return false;
   const reached=new Set(),todo=[t.transaction.hash];while(todo.length){const id=todo.pop();if(reached.has(id))continue;const n=nodes.get(id);if(!n)return false;reached.add(id);const o=n.outcome;if('Unknown' in o.status||new Set(o.receipt_ids).size!==o.receipt_ids.length||('SuccessReceiptId' in o.status&&!o.receipt_ids.includes(o.status.SuccessReceiptId)))return false;todo.push(...o.receipt_ids);}
   if(reached.size!==nodes.size)return false;
   const degrees=new Map(rows.map(n=>[n.id,0]));for(const n of rows)for(const id of n.outcome.receipt_ids)degrees.set(id,degrees.get(id)+1);const roots=[...degrees].filter(([,n])=>n===0).map(([id])=>id);let count=0;while(roots.length){const id=roots.pop();count++;for(const c of nodes.get(id).outcome.receipt_ids){const n=degrees.get(c)-1;degrees.set(c,n);if(n===0)roots.push(c);}}if(count!==nodes.size)return false;
  }return true;
 };
 if(!keys(r,'format recording_id recording_sha256 assessor_sha256 network source asset vault conclusion steps assumptions meaning units new_model_calls new_transactions')||r.format!=='agent-crash-lab/token-review-v2'||r.recording_sha256!==inputHash||r.assessor_sha256!==assessorHash||r.recording_id!==input.id||r.network!==input.network||r.vault!==input.vault||!equal(r.source,input.source)||!equal(r.asset,input.asset)||!state(r.conclusion)||r.new_model_calls!==0||r.new_transactions!==0||!Array.isArray(r.assumptions)||r.assumptions.length!==3||!r.assumptions.every(x=>typeof x==='string'&&x.length<500)||typeof r.meaning!=='string'||typeof r.units!=='string'||!Array.isArray(r.steps)||r.steps.length!==input.steps.length)fail();
 for(let i=0;i<r.steps.length;i++){
  const s=r.steps[i],original=input.steps[i];
  if(!keys(s,'id operation source_pointer before after held_delta rights_delta gross_in gross_out event_net parity_difference transfer_out rights_debit_without_transfer backing_shortfall state_event_agreement ledger_relation backing conclusion reasons events ignored_event_logs transaction_ids')||s.id!==original.id||s.operation!==original.operation||s.source_pointer!==original.source_pointer||!equal(s.before,original.before)||!equal(s.after,original.after)||!state(s.conclusion)||!Array.isArray(s.reasons)||!s.reasons.every(x=>typeof x==='string'&&x.length<500)||!Array.isArray(s.events)||!Number.isSafeInteger(s.ignored_event_logs)||s.ignored_event_logs<0||!equal(s.transaction_ids,original.transactions.map(t=>t.result.transaction.hash)))fail();
  for(const key of ['held_delta','rights_delta','event_net','parity_difference'])if(!integer(s[key]))fail();
  for(const key of ['gross_in','gross_out','transfer_out'])if(!unsigned(s[key]))fail();
  for(const key of ['rights_debit_without_transfer','backing_shortfall'])if(s[key]!==null&&!unsigned(s[key]))fail();
  if(!completeCapture(original)&&!s.reasons.length)fail();
  let incoming=0n,outgoing=0n,transferOut=0n;const seen=new Set();
  for(const e of s.events){
   if(!keys(e,'kind amount old_owner_id new_owner_id receipt_id transaction_id log_index data_index source_pointer executor_id')||!['ft_transfer','ft_mint','ft_burn'].includes(e.kind)||!unsigned(e.amount)||e.executor_id!==r.asset.contract||!Number.isSafeInteger(e.log_index)||e.log_index<0||!Number.isSafeInteger(e.data_index)||e.data_index<0)fail();
   const key=e.receipt_id+':'+e.log_index+':'+e.data_index;if(seen.has(key))fail();seen.add(key);
   const tx=original.transactions.find(t=>t.result.transaction.hash===e.transaction_id);if(!tx)fail();
   const nodes=[tx.result.transaction_outcome,...tx.result.receipts_outcome],n=nodes.findIndex(n=>n.id===e.receipt_id);if(n<0)fail();
   const node=nodes[n],o=node.outcome;let event;try{const log=o.logs[e.log_index];if(!log?.startsWith('EVENT_JSON:'))fail();event=JSON.parse(log.slice(11));}catch{fail();}
   const datum=event.data?.[e.data_index],pointer=tx.source_pointer+(n===0?'/transaction_outcome':'/receipts_outcome/'+(n-1))+'/outcome/logs/'+e.log_index;
   if(o.executor_id!==r.asset.contract||!Object.keys(o.status).some(k=>['SuccessReceiptId','SuccessValue'].includes(k))||event.standard!=='nep141'||event.version!=='1.0.0'||event.event!==e.kind||datum?.amount!==e.amount||(datum?.old_owner_id??null)!==e.old_owner_id||(datum?.new_owner_id??null)!==e.new_owner_id||e.source_pointer!==pointer)fail();
   if(e.new_owner_id===r.vault&&e.old_owner_id!==r.vault)incoming+=BigInt(e.amount);if(e.old_owner_id===r.vault&&e.new_owner_id!==r.vault){outgoing+=BigInt(e.amount);if(e.kind==='ft_transfer')transferOut+=BigInt(e.amount);}
  }
  const rights=b=>BigInt(b.credit)+BigInt(b.pending)+BigInt(b.reserved),delta=BigInt(s.after.held)-BigInt(s.before.held),change=rights(s.after)-rights(s.before),net=incoming-outgoing;
  if(String(delta)!==s.held_delta||String(change)!==s.rights_delta||String(net)!==s.event_net||String(incoming)!==s.gross_in||String(outgoing)!==s.gross_out||String(transferOut)!==s.transfer_out||String(delta-change)!==s.parity_difference)fail();
  const evidence=s.reasons.length?'unknown':delta===net?'agrees':'contradicts';if(evidence!==s.state_event_agreement)fail();
  const unmatched=evidence==='agrees'?String(-change>transferOut?-change-transferOut:0n):null,deficits=[0n,...[s.before,s.after].map(b=>BigInt(b.liabilities)-BigInt(b.held))],shortfall=s.reasons.length?null:String(deficits.reduce((a,b)=>a>b?a:b));
  if(s.rights_debit_without_transfer!==unmatched||s.backing_shortfall!==shortfall)fail();
  const relation=evidence!=='agrees'?'unknown':delta===change?'matched':'different';
  const backing=s.reasons.length?'unknown':[s.before,s.after].some(b=>BigInt(b.held)<BigInt(b.liabilities))?'insufficient':'sufficient';
  const conclusion=s.reasons.length?'inconclusive':evidence==='contradicts'?'recorded-evidence-conflict':relation==='different'||backing==='insufficient'?'recorded-gap':'recorded-parity';
  if(s.ledger_relation!==relation||s.backing!==backing||s.conclusion!==conclusion)fail();
 }
 const conclusion=['recorded-evidence-conflict','recorded-gap','inconclusive'].find(state=>r.steps.some(s=>s.conclusion===state))||'recorded-parity';if(r.conclusion!==conclusion)fail();return r;
}
async function validateSourceCheck(value,review,meta){
 const fail=()=>{throw Error('The source-check response does not match this recording and release. No corroboration result has been accepted.');};
 const entry=meta?.cases?.find(c=>c.recordingSha256===review?.recording_sha256);
 const expected=['format','status','recordingSha256','corroboration','provider','network','capturedReadRequests','capturedAtStart','capturedAtEnd','replayNetworkCalls','transactionSubmissions','contractExecutions','signatureOrStateProofVerified','independentGrading','datasetSha256','verifierSha256','meaning'];
 if(!entry||review.format!=='agent-crash-lab/token-review-v2'||!value||Object.keys(value).sort().join('|')!==expected.sort().join('|')||value.format!=='agent-crash-lab/source-check-v1'||value.status!=='replayed'||value.recordingSha256!==review.recording_sha256||value.corroboration?.recordingSha256!==review.recording_sha256||value.corroboration?.case!==review.recording_id||value.verifierSha256!==meta.verifierSha256||value.datasetSha256!==meta.datasetSha256||value.provider!=='https://archival-rpc.testnet.near.org'||value.network!=='testnet'||value.capturedReadRequests!==25||value.replayNetworkCalls!==0||value.transactionSubmissions!==0||value.contractExecutions!==0||value.signatureOrStateProofVerified!==false||value.independentGrading!==false)fail();
 // This is a sealed two-case replay, not a general grader. Bind every nested field to the published expected response, including receipt links and operation-reference results.
 const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
 const bytes=new TextEncoder().encode(JSON.stringify(sorted(value))),digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
 if(digest!==entry.expectedResponseSha256)fail();return value;
}
// All imported text is rendered as text, never executable HTML or Python.
const el=id=>document.getElementById(id),browserMode=new URLSearchParams(location.search).get('browser')==='1'||!['127.0.0.1','localhost'].includes(location.hostname);
if(browserMode)for(const link of document.querySelectorAll('a[href="./"]'))link.href='./?browser=1';
let catalog,worker,pending,sequence=0,busy=false,recordingBytes,report,sessionToken;
const labels={'recorded-parity':'Net custody and rights match','recorded-gap':'Custody and rights changed differently','recorded-evidence-conflict':'The evidence does not reconcile','inconclusive':'Evidence is incomplete'};
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
const visible=value=>String(value??'').replace(/[\p{Cc}\p{Bidi_Control}]/gu,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
const number=value=>value===null?'unknown':BigInt(value).toLocaleString('en-US');
function node(tag,value){const n=document.createElement(tag);if(value!==undefined)n.textContent=visible(value);return n;}
function busyState(value,text){busy=value;for(const id of ['recording','run-token','token-upload','token-download','token-input','source-verify'])el(id).disabled=value;el('token-status').textContent=text;}
function clearSource(){el('source-panel').hidden=true;el('source-error').hidden=true;el('source-results').hidden=true;el('source-results').replaceChildren();el('source-raw-panel').hidden=true;el('source-raw').textContent='';}
function clear(){report=null;recordingBytes=null;el('token-results').hidden=true;el('token-error').hidden=true;el('token-proofs').replaceChildren();clearSource();}
function resetWorker(message){worker?.terminate();worker=null;if(pending){clearTimeout(pending.timer);pending.reject(Error(message));pending=null;}}
function browserOperation(path,body){
 if(!worker){worker=new Worker('browser-worker.js?bundle=lab-v9');worker.onmessage=({data})=>{if(!pending||data.id!==pending.id)return;if(data.progress){el('token-status').textContent=data.progress;return;}const job=pending;pending=null;clearTimeout(job.timer);if(data.error!==undefined){worker.terminate();worker=null;job.reject(Error(data.error));}else job.resolve(data.result);};worker.onerror=()=>resetWorker('Browser Python stopped. Retry the review or use the offline ZIP.');}
 return new Promise((resolve,reject)=>{const id=++sequence;pending={id,resolve,reject,timer:setTimeout(()=>resetWorker('Browser setup took too long. Retry or use the offline ZIP.'),90000)};worker.postMessage({id,path,body});});
}
function save(name,bytes){const url=URL.createObjectURL(new Blob([bytes],{type:'application/json'})),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function render(r){
 el('recording-id').textContent=visible(r.recording_id);el('review-title').textContent=labels[r.conclusion];el('token-finding').dataset.state=r.conclusion;
 el('recording-kind').textContent=r.source.kind==='synthetic-control'?'Constructed control · no new chain observation':r.source.kind==='owner-recording'?'Owner-supplied recording':'Published third-party capture';
 const finding=el('token-finding');finding.replaceChildren();const debit=r.steps.find(s=>s.rights_debit_without_transfer!==null&&BigInt(s.rights_debit_without_transfer)>0n),gap=r.steps.find(s=>s.state_event_agreement==='agrees'&&s.parity_difference!=='0');
 finding.append(node('strong',debit?number(debit.rights_debit_without_transfer)+' units debited without a matching transfer':gap?number(gap.parity_difference)+' units of custody / rights difference':r.conclusion==='inconclusive'?'Keep the conclusion open':labels[r.conclusion]));
 finding.append(node('p',debit?'Recorded rights fell by '+number(-BigInt(debit.rights_delta))+' units; transfers out account for at most '+number(debit.transfer_out)+'. The vault reports '+number(debit.after.held)+' units afterward. A stated operation reference determines whether the unmatched debit is a failed obligation or an intended writeoff.':gap?'Vault tokens changed by '+number(gap.held_delta)+' units; recorded rights changed by '+number(gap.rights_delta)+'. Capital top-ups, fees or reallocations can create a difference. A gap alone does not prove lost entitlement.':r.conclusion==='recorded-parity'?'The recorded net changes agree under the declared assumptions. Matching changes do not by themselves prove authorization or successful delivery.':'Missing receipts, uncertain identity or contradictory observations leave the payment explanation open.'));
 el('token-steps').replaceChildren();el('token-proofs').replaceChildren();
 r.steps.forEach((s,i)=>{
  const tr=node('tr'),name=node('td',(i+1)+'. '+s.operation);name.append(node('small',s.id));tr.append(name,node('td',number(s.held_delta)),node('td',number(s.rights_delta)));
  const flow=node('td','In '+number(s.gross_in)+' / out '+number(s.gross_out));flow.append(node('small','Transfers out '+number(s.transfer_out)),node('small',s.events.length+' custody event(s)'));tr.append(flow);
  const result=node('td',labels[s.conclusion]),link=node('a','Inspect evidence ↓');link.href='#proof-'+i;result.append(node('small',s.backing==='sufficient'?'Backing sufficient':s.backing==='insufficient'?'Backing insufficient':'Backing unknown'),link);tr.append(result);el('token-steps').append(tr);
  const detail=node('details');detail.className='token-proof';detail.id='proof-'+i;detail.append(node('summary',(i+1)+'. '+s.operation+' · '+labels[s.conclusion]));
  detail.append(node('p',s.reasons.length?s.reasons.join(' '):s.state_event_agreement==='contradicts'?'The endpoint custody change and captured token events disagree. This does not establish which observation is wrong.':s.ledger_relation==='different'?'The two net changes differ. Interpret that difference with the operation reference, not as automatic lost entitlement.':'The two net changes match; the operation reference remains a separate check.'));
  const dl=node('dl');for(const [k,v] of [['State / event agreement',s.state_event_agreement],['Net custody / rights relation',s.ledger_relation],['Rights debit unmatched by transfers',s.rights_debit_without_transfer===null?'unknown':number(s.rights_debit_without_transfer)],['Largest endpoint backing shortfall',s.backing_shortfall===null?'unknown':number(s.backing_shortfall)],['Endpoint blocks',s.before.block_height+' → '+s.after.block_height],['Original step pointer',s.source_pointer],['Transaction IDs',s.transaction_ids.join(', ')||'Missing'],['Ignored foreign or failed-receipt event logs',s.ignored_event_logs]])dl.append(node('dt',k),node('dd',v));detail.append(dl);
  const pre=node('pre');pre.textContent=JSON.stringify(s.events,null,2);pre.tabIndex=0;pre.setAttribute('aria-label','Recorded token events for step '+(i+1));detail.append(pre);el('token-proofs').append(detail);link.onclick=()=>{detail.open=true;};
 });
 el('token-assumptions').replaceChildren(...r.assumptions.map(x=>node('li',x)));el('token-meaning').textContent=r.meaning+' '+r.units;
 const dl=el('token-source');dl.replaceChildren();for(const [k,v] of [['Network / asset',r.network+' / '+r.asset.contract],['Vault',r.vault],['Original source',r.source.url],['Original archive SHA-256',r.source.sha256],['Exact recording SHA-256',r.recording_sha256],['Reviewer SHA-256',r.assessor_sha256],['Recorded code SHA-256',r.asset.sha256]])dl.append(node('dt',k),node('dd',v));
 const url=new URL(r.source.url,location.href);if(url.protocol==='https:'&&url.hostname==='github.com'){const a=node('a','Open pinned original archive ↗');a.href=url.href;a.rel='noreferrer';dl.append(node('dt','Public source'),a);}
 el('token-raw').textContent=JSON.stringify(r,null,2);el('token-results').hidden=false;el('source-panel').hidden=!catalog.sourceCorroboration?.cases.some(c=>c.recordingSha256===r.recording_sha256);
}
async function run(bytes){
 if(busy)return;clear();busyState(true,'Reading the recording…');
 try{
  if(!bytes?.length||bytes.length>2*1024*1024)throw Error('Choose a nonempty token-recording-v1 JSON file no larger than 2 MiB.');
  let input;try{input=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{throw Error('Choose a valid UTF-8 JSON token recording. The selected file could not be read as JSON.');}let result;
  if(browserMode)result=await browserOperation('/api/token-review',bytes);
  else{const response=await fetch('/api/token-review',{method:'POST',headers:{'Content-Type':'application/json','X-CrashLab-Token':sessionToken},body:bytes});result=await response.json();if(!response.ok||result.error)throw Error(result.error||'The local review could not finish. Restart the workbench and retry.');}
  validateTokenReport(result,input,await digest(bytes),catalog.assessorSha256);recordingBytes=bytes;report=result;render(result);busyState(false,'Review complete · '+(browserMode?'Python in this browser':'local Python')+' · no new transaction or model call.');el('review-title').focus();
 }catch(e){clear();el('token-error').hidden=false;el('token-error').textContent=visible(e.message||'The recording could not be reviewed.');busyState(false,'No result accepted. Correct the file or retry the review.');}
}
async function example(){
 if(busy)return;clear();busyState(true,'Loading the selected recording…');
 try{const entry=catalog.recordings.find(x=>x.id===el('recording').value);if(!entry)throw Error('Choose a recorded example.');const response=await fetch(browserMode?new URL('../'+entry.path,location.href):'/api/token-recording?case='+encodeURIComponent(entry.id));if(!response.ok)throw Error('The example could not be downloaded. Retry or use the offline ZIP.');const bytes=new Uint8Array(await response.arrayBuffer());if(bytes.length!==entry.bytes||await digest(bytes)!==entry.sha256)throw Error('The example does not match this release. Reload and retry after the update completes.');busyState(false,'Recording loaded.');await run(bytes);}catch(e){clear();el('token-error').hidden=false;el('token-error').textContent=visible(e.message);busyState(false,'No result accepted. Retry loading the example.');}
}
el('run-token').onclick=example;el('recording').onchange=()=>{if(!busy){clear();el('token-status').textContent='Selection changed. Review the selected recording.';}};
el('token-upload').onchange=async event=>{const file=event.target.files[0];if(!file||busy)return;clear();if(file.size>2*1024*1024){el('token-error').hidden=false;el('token-error').textContent='Choose a token recording no larger than 2 MiB.';return;}busyState(true,'Reading the selected file…');try{const bytes=new Uint8Array(await file.arrayBuffer());busyState(false,'File loaded.');await run(bytes);}catch{busyState(false,'File could not be read.');el('token-error').hidden=false;el('token-error').textContent='The file could not be read. Select it again.';}finally{event.target.value='';}};
el('token-download').onclick=()=>{if(!busy&&report)save('token-review.json',JSON.stringify(report,null,2));};el('token-input').onclick=()=>{if(!busy&&recordingBytes)save('token-recording.json',recordingBytes);};
function renderSource(value){
 const box=el('source-results'),c=value.corroboration,reference=c.operationReference;box.replaceChildren();
 const title=node('h3',reference.status==='failed'?'Payout reference failed':reference.status==='passed'?'Payout reference passed':'Payout reference is inconclusive');title.dataset.state=reference.status;title.tabIndex=-1;box.append(title,node('p',reference.reference));
 box.append(node('p',reference.status==='failed'?'The root transaction succeeded, but its token payout receipt failed. Recorded rights were reduced anyway. Root success is not completed delivery.':reference.status==='passed'?'The saved sources show the reserved payment delivered to the recorded owner, with one corresponding rights debit.':reference.reason));
 const metrics=node('dl');metrics.className='source-metrics';for(const [k,v] of [['Expected rights afterward',number(reference.expectedRightsAfter)],['Observed rights afterward',number(reference.observedRightsAfter)],['Expected / observed delivery',number(reference.expectedTokenDelivery)+' / '+number(reference.observedTokenDelivery)]]){const group=node('div');group.append(node('dt',k),node('dd',v));metrics.append(group);}box.append(metrics);
 const trace=node('details');trace.className='token-proof';trace.append(node('summary','Receipt IDs and source fingerprints'));const dl=node('dl');for(const [k,v] of [['Source collection window',value.capturedAtStart+' → '+value.capturedAtEnd],['Transaction ID',c.transactionId],['Payout receipt ID',reference.payout?.receiptId??'Missing'],['Dataset SHA-256',value.datasetSha256],['Verifier SHA-256',value.verifierSha256]])dl.append(node('dt',k),node('dd',v));trace.append(dl);box.append(trace);
 for(const p of c.points){const detail=node('details');detail.className='token-proof';detail.append(node('summary',p.side+' · block '+p.blockHeight));const facts=node('dl');for(const [k,v] of Object.entries(p.fields))facts.append(node('dt',k),node('dd',number(v)));detail.append(facts);
  for(const q of p.rawQueries){const a=node('a','Open '+q.kind+' response ↗'),path='verification/rpc-study/'+q.folder+'/response.json';a.href=browserMode?new URL('../'+path,location.href).href:'/api/token-source-file?name='+encodeURIComponent(path);a.target='_blank';a.rel='noreferrer';detail.append(node('p',q.responseSha256),a);}box.append(detail);}
 if(reference.payout){const p=node('p','Child payout · '+reference.payout.outcome+' · '+reference.payout.method+' '+number(reference.payout.amount)+' atomic units'),path='verification/rpc-study/'+c.receiptDetailsCapture+'/response.json';const a=node('a','Open the receipt-body response ↗');a.href=browserMode?new URL('../'+path,location.href).href:'/api/token-source-file?name='+encodeURIComponent(path);a.target='_blank';a.rel='noreferrer';box.append(p,a);}
 const download=node('button','Save source check');download.onclick=()=>{if(!busy)save('source-check.json',JSON.stringify(value,null,2));};box.append(download);
 box.append(node('p','This replays 25 saved read-only requests; it performs no live chain query. The public endpoint, storage schemas and operation reference are trusted. No signature/state proof or independent grading is established.'));
 el('source-raw').textContent=JSON.stringify(value,null,2);el('source-raw-panel').hidden=false;box.hidden=false;title.focus();
}
el('source-verify').onclick=async()=>{
 if(busy||!report)return;const selected=report;el('source-error').hidden=true;el('source-results').hidden=true;el('source-raw-panel').hidden=true;busyState(true,'Replaying saved source observations…');
 try{const body={recording_sha256:selected.recording_sha256};let value;if(browserMode)value=await browserOperation('/api/token-source-check',body);else{const response=await fetch('/api/token-source-check',{method:'POST',headers:{'Content-Type':'application/json','X-CrashLab-Token':sessionToken},body:JSON.stringify(body)});value=await response.json();if(!response.ok||value.error)throw Error(value.error||'The source check could not finish. Retry or use the offline verifier.');}await validateSourceCheck(value,selected,catalog.sourceCorroboration);if(report!==selected)throw Error('The recording changed. Replay its source check again.');renderSource(value);busyState(false,'Source check replay complete · no new RPC, model call or transaction.');}
 catch(error){el('source-results').hidden=true;el('source-raw-panel').hidden=true;el('source-error').hidden=false;el('source-error').textContent=visible(error.message||'The source check could not finish.');busyState(false,'No source corroboration accepted. The conditional recording review remains separate.');}
};
function theme(){el('theme-toggle').textContent=document.documentElement.dataset.theme==='light'?'Use dark theme':'Use light theme';}
try{if(localStorage.getItem('crash-lab-theme')==='light')document.documentElement.dataset.theme='light';}catch{}theme();el('theme-toggle').onclick=()=>{const next=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=next;try{localStorage.setItem('crash-lab-theme',next);}catch{}theme();};
(async()=>{try{
 el('runtime').textContent=browserMode?'Browser Python':'Local Python';
 if(browserMode){const response=await fetch('catalog.json',{cache:'reload'});if(!response.ok)throw Error('The example list could not load. Reload to retry.');const c=await response.json(),source=c.sourceCorroboration;catalog={recordings:c.tokenRecordings.map(x=>({...x,...c.files[x.path]})),assessorSha256:c.files['token_review.py'].sha256,sourceCorroboration:{...source,verifierSha256:c.files[source.module].sha256,hashes:Object.fromEntries(source.files.map(p=>[p,c.files[p].sha256]))}};}
 else{const [a,b]=await Promise.all([fetch('/api/token-catalog'),fetch('/api/catalog')]);if(!a.ok||!b.ok)throw Error('The local workbench could not load. Restart it and reload this page.');catalog=await a.json();sessionToken=(await b.json()).sessionToken;}
 el('recording').replaceChildren(...catalog.recordings.map(r=>{const option=node('option',r.title);option.value=r.id;return option;}));const selected=new URLSearchParams(location.search).get('case');if(catalog.recordings.some(x=>x.id===selected))el('recording').value=selected;busyState(false,'Choose an example or import a token-recording-v1 file.');
 }catch(e){el('token-error').hidden=false;el('token-error').textContent=visible(e.message);el('token-status').textContent='Setup incomplete. Reload to retry.';}})();
