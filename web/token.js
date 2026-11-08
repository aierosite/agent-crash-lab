'use strict';
function validateTokenReport(r,input,inputHash,assessorHash){
 const fail=()=>{throw Error('The review response is incomplete or disagrees with this recording. Retry the review; no result has been accepted.');};
 const keys=(o,list)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join('|')===list.split(' ').sort().join('|');
 const equal=(a,b)=>{if(a===b)return true;if(!a||!b||typeof a!=='object'||typeof b!=='object')return false;const ka=Object.keys(a).sort(),kb=Object.keys(b).sort();return ka.length===kb.length&&ka.every((k,i)=>k===kb[i]&&equal(a[k],b[k]));};
 const integer=x=>typeof x==='string'&&/^-?(0|[1-9]\d{0,48})$/.test(x)&&x!=='-0'&&BigInt(x)>-(2n**160n)&&BigInt(x)<2n**160n;
 const unsigned=x=>integer(x)&&!x.startsWith('-');
 const state=x=>['recorded-consistent','recorded-inconsistency','inconclusive'].includes(x);
 if(!keys(r,'format recording_id recording_sha256 assessor_sha256 network source asset vault conclusion steps assumptions meaning units new_model_calls new_transactions')||r.format!=='agent-crash-lab/token-review-v1'||r.recording_sha256!==inputHash||r.assessor_sha256!==assessorHash||r.recording_id!==input.id||r.network!==input.network||r.vault!==input.vault||!equal(r.source,input.source)||!equal(r.asset,input.asset)||!state(r.conclusion)||r.new_model_calls!==0||r.new_transactions!==0||!Array.isArray(r.assumptions)||r.assumptions.length!==3||!r.assumptions.every(x=>typeof x==='string'&&x.length<500)||typeof r.meaning!=='string'||typeof r.units!=='string'||!Array.isArray(r.steps)||r.steps.length!==input.steps.length)fail();
 for(let i=0;i<r.steps.length;i++){
  const s=r.steps[i],original=input.steps[i];
  if(!keys(s,'id operation source_pointer before after held_delta rights_delta gross_in gross_out event_net entitlement_reduction unfunded_rights state_event_agreement rights_conservation backing conclusion reasons events ignored_event_logs transaction_ids')||s.id!==original.id||s.operation!==original.operation||s.source_pointer!==original.source_pointer||!equal(s.before,original.before)||!equal(s.after,original.after)||!state(s.conclusion)||!Array.isArray(s.reasons)||!s.reasons.every(x=>typeof x==='string'&&x.length<500)||!Array.isArray(s.events)||!Number.isSafeInteger(s.ignored_event_logs)||s.ignored_event_logs<0||!equal(s.transaction_ids,original.transactions.map(t=>t.result.transaction.hash)))fail();
  for(const key of ['held_delta','rights_delta','event_net'])if(!integer(s[key]))fail();
  for(const key of ['gross_in','gross_out'])if(!unsigned(s[key]))fail();
  for(const key of ['entitlement_reduction','unfunded_rights'])if(s[key]!==null&&!unsigned(s[key]))fail();
  let incoming=0n,outgoing=0n;const seen=new Set();
  for(const e of s.events){
   if(!keys(e,'kind amount old_owner_id new_owner_id receipt_id transaction_id log_index data_index source_pointer executor_id')||!['ft_transfer','ft_mint','ft_burn'].includes(e.kind)||!unsigned(e.amount)||e.executor_id!==r.asset.contract||!Number.isSafeInteger(e.log_index)||e.log_index<0||!Number.isSafeInteger(e.data_index)||e.data_index<0)fail();
   const key=e.receipt_id+':'+e.log_index+':'+e.data_index;if(seen.has(key))fail();seen.add(key);
   const tx=original.transactions.find(t=>t.result.transaction.hash===e.transaction_id);if(!tx)fail();
   const nodes=[tx.result.transaction_outcome,...tx.result.receipts_outcome],n=nodes.findIndex(n=>n.id===e.receipt_id);if(n<0)fail();
   const node=nodes[n],o=node.outcome;let event;try{const log=o.logs[e.log_index];if(!log?.startsWith('EVENT_JSON:'))fail();event=JSON.parse(log.slice(11));}catch{fail();}
   const datum=event.data?.[e.data_index],pointer=tx.source_pointer+(n===0?'/transaction_outcome':'/receipts_outcome/'+(n-1))+'/outcome/logs/'+e.log_index;
   if(o.executor_id!==r.asset.contract||!Object.keys(o.status).some(k=>['SuccessReceiptId','SuccessValue'].includes(k))||event.standard!=='nep141'||event.version!=='1.0.0'||event.event!==e.kind||datum?.amount!==e.amount||(datum?.old_owner_id??null)!==e.old_owner_id||(datum?.new_owner_id??null)!==e.new_owner_id||e.source_pointer!==pointer)fail();
   if(e.new_owner_id===r.vault)incoming+=BigInt(e.amount);if(e.old_owner_id===r.vault)outgoing+=BigInt(e.amount);
  }
  const rights=b=>BigInt(b.credit)+BigInt(b.pending)+BigInt(b.reserved),delta=BigInt(s.after.held)-BigInt(s.before.held),change=rights(s.after)-rights(s.before),net=incoming-outgoing;
  if(String(delta)!==s.held_delta||String(change)!==s.rights_delta||String(net)!==s.event_net||String(incoming)!==s.gross_in||String(outgoing)!==s.gross_out)fail();
  const evidence=s.reasons.length?'unknown':delta===net?'agrees':'contradicts';if(evidence!==s.state_event_agreement)fail();
  const reduction=evidence==='agrees'?String(delta>change?delta-change:0n):null,creation=evidence==='agrees'?String(change>delta?change-delta:0n):null;
  if(s.entitlement_reduction!==reduction||s.unfunded_rights!==creation)fail();
  const conservation=evidence!=='agrees'?'unknown':reduction!=='0'?'reduced_without_payment':creation!=='0'?'increased_without_backing':'preserved';
  const backing=s.reasons.length?'unknown':[s.before,s.after].some(b=>BigInt(b.held)<BigInt(b.liabilities))?'insufficient':'sufficient';
  const conclusion=s.reasons.length?'inconclusive':evidence==='contradicts'||conservation!=='preserved'||backing==='insufficient'?'recorded-inconsistency':'recorded-consistent';
  if(s.rights_conservation!==conservation||s.backing!==backing||s.conclusion!==conclusion)fail();
 }
 const conclusion=r.steps.some(s=>s.conclusion==='recorded-inconsistency')?'recorded-inconsistency':r.steps.some(s=>s.conclusion==='inconclusive')?'inconclusive':'recorded-consistent';if(r.conclusion!==conclusion)fail();return r;
}
// All imported text is rendered as text, never executable HTML or Python.
const el=id=>document.getElementById(id),browserMode=new URLSearchParams(location.search).get('browser')==='1'||!['127.0.0.1','localhost'].includes(location.hostname);
if(browserMode)for(const link of document.querySelectorAll('a[href="./"]'))link.href='./?browser=1';
let catalog,worker,pending,sequence=0,busy=false,recordingBytes,report,sessionToken;
const labels={'recorded-consistent':'Recorded facts agree','recorded-inconsistency':'A recorded inconsistency','inconclusive':'Evidence is incomplete'};
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
const visible=value=>String(value??'').replace(/[\p{Cc}\p{Bidi_Control}]/gu,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
const number=value=>value===null?'unknown':BigInt(value).toLocaleString('en-US');
function node(tag,value){const n=document.createElement(tag);if(value!==undefined)n.textContent=visible(value);return n;}
function busyState(value,text){busy=value;for(const id of ['recording','run-token','token-upload','token-download','token-input'])el(id).disabled=value;el('token-status').textContent=text;}
function clear(){report=null;recordingBytes=null;el('token-results').hidden=true;el('token-error').hidden=true;el('token-proofs').replaceChildren();}
function resetWorker(message){worker?.terminate();worker=null;if(pending){clearTimeout(pending.timer);pending.reject(Error(message));pending=null;}}
function browserReview(bytes){
 if(!worker){worker=new Worker('browser-worker.js?bundle=lab-v8');worker.onmessage=({data})=>{if(!pending||data.id!==pending.id)return;if(data.progress){el('token-status').textContent=data.progress;return;}const job=pending;pending=null;clearTimeout(job.timer);if(data.error!==undefined){worker.terminate();worker=null;job.reject(Error(data.error));}else job.resolve(data.result);};worker.onerror=()=>resetWorker('Browser Python stopped. Retry the review or use the offline ZIP.');}
 return new Promise((resolve,reject)=>{const id=++sequence;pending={id,resolve,reject,timer:setTimeout(()=>resetWorker('Browser setup took too long. Retry or use the offline ZIP.'),90000)};worker.postMessage({id,path:'/api/token-review',body:bytes});});
}
function save(name,bytes){const url=URL.createObjectURL(new Blob([bytes],{type:'application/json'})),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function render(r){
 el('recording-id').textContent=visible(r.recording_id);el('review-title').textContent=labels[r.conclusion];el('token-finding').dataset.state=r.conclusion;
 const finding=el('token-finding');finding.replaceChildren();const loss=r.steps.find(s=>s.entitlement_reduction!==null&&BigInt(s.entitlement_reduction)>0n);
 finding.append(node('strong',loss?number(loss.entitlement_reduction)+' units of rights unexplained':r.conclusion==='inconclusive'?'Keep the conclusion open':r.conclusion==='recorded-inconsistency'?'The recorded facts do not reconcile':'Custody and rights reconcile'));
 finding.append(node('p',loss?'The vault still reports '+number(loss.after.held)+' token units. User rights fall from '+number(BigInt(loss.before.credit)+BigInt(loss.before.pending)+BigInt(loss.before.reserved))+' to '+number(BigInt(loss.after.credit)+BigInt(loss.after.pending)+BigInt(loss.after.reserved))+', while the recorded token movement is '+number(loss.event_net)+'. Sufficient backing alone misses this discrepancy.':r.conclusion==='recorded-consistent'?'Within the declared single-owner and closed-interval assumptions, the recorded movements account for the change in user rights. This does not establish authorization or overall safety.':'Read the step evidence before drawing a payment conclusion. Missing receipts, uncertain identity or contradictory summaries cannot prove that a right was paid.'));
 el('token-steps').replaceChildren();el('token-proofs').replaceChildren();
 r.steps.forEach((s,i)=>{
  const tr=node('tr'),name=node('td',(i+1)+'. '+s.operation);name.append(node('small',s.id));tr.append(name,node('td',number(s.held_delta)),node('td',number(s.rights_delta)));
  const flow=node('td','In '+number(s.gross_in)+' / out '+number(s.gross_out));flow.append(node('small',s.events.length+' custody event(s)'));tr.append(flow);
  const result=node('td',labels[s.conclusion]),link=node('a','Inspect evidence ↓');link.href='#proof-'+i;result.append(node('small',s.backing==='sufficient'?'Backing sufficient':s.backing==='insufficient'?'Backing insufficient':'Backing unknown'),link);tr.append(result);el('token-steps').append(tr);
  const detail=node('details');detail.className='token-proof';detail.id='proof-'+i;detail.append(node('summary',(i+1)+'. '+s.operation+' · '+labels[s.conclusion]));
  detail.append(node('p',s.reasons.length?s.reasons.join(' '):s.rights_conservation==='reduced_without_payment'?'Rights decreased without matching recorded token movement. This is an entitlement discrepancy even though the vault reports enough backing.':s.state_event_agreement==='contradicts'?'The endpoint custody change and captured token events disagree. This does not prove that the missing payment happened.':'Recorded custody and rights changes agree under the declared assumptions.'));
  const dl=node('dl');for(const [k,v] of [['State / event agreement',s.state_event_agreement],['Rights conservation',s.rights_conservation],['Endpoint blocks',s.before.block_height+' → '+s.after.block_height],['Original step pointer',s.source_pointer],['Transaction IDs',s.transaction_ids.join('\n')||'Missing'],['Ignored foreign or failed-receipt event logs',s.ignored_event_logs]])dl.append(node('dt',k),node('dd',v));detail.append(dl);
  const pre=node('pre');pre.textContent=JSON.stringify(s.events,null,2);pre.tabIndex=0;pre.setAttribute('aria-label','Recorded token events for step '+(i+1));detail.append(pre);el('token-proofs').append(detail);link.onclick=()=>{detail.open=true;};
 });
 el('token-assumptions').replaceChildren(...r.assumptions.map(x=>node('li',x)));el('token-meaning').textContent=r.meaning+' '+r.units;
 const dl=el('token-source');dl.replaceChildren();for(const [k,v] of [['Network / asset',r.network+' / '+r.asset.contract],['Vault',r.vault],['Original source',r.source.url],['Original archive SHA-256',r.source.sha256],['Exact recording SHA-256',r.recording_sha256],['Reviewer SHA-256',r.assessor_sha256],['Recorded code SHA-256',r.asset.sha256]])dl.append(node('dt',k),node('dd',v));
 const url=new URL(r.source.url,location.href);if(url.protocol==='https:'&&url.hostname==='github.com'){const a=node('a','Open pinned original archive ↗');a.href=url.href;a.rel='noreferrer';dl.append(node('dt','Public source'),a);}
 el('token-raw').textContent=JSON.stringify(r,null,2);el('token-results').hidden=false;
}
async function run(bytes){
 if(busy)return;clear();busyState(true,'Reading the recording…');
 try{
  if(!bytes?.length||bytes.length>2*1024*1024)throw Error('Choose a nonempty token-recording-v1 JSON file no larger than 2 MiB.');
  let input;try{input=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{throw Error('Choose a valid UTF-8 JSON token recording. The selected file could not be read as JSON.');}let result;
  if(browserMode)result=await browserReview(bytes);
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
function theme(){el('theme-toggle').textContent=document.documentElement.dataset.theme==='light'?'Use dark theme':'Use light theme';}
try{if(localStorage.getItem('crash-lab-theme')==='light')document.documentElement.dataset.theme='light';}catch{}theme();el('theme-toggle').onclick=()=>{const next=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=next;try{localStorage.setItem('crash-lab-theme',next);}catch{}theme();};
(async()=>{try{
 el('runtime').textContent=browserMode?'Browser Python':'Local Python';
 if(browserMode){const response=await fetch('catalog.json',{cache:'reload'});if(!response.ok)throw Error('The example list could not load. Reload to retry.');const c=await response.json();catalog={recordings:c.tokenRecordings.map(x=>({...x,...c.files[x.path]})),assessorSha256:c.files['token_review.py'].sha256};}
 else{const [a,b]=await Promise.all([fetch('/api/token-catalog'),fetch('/api/catalog')]);if(!a.ok||!b.ok)throw Error('The local workbench could not load. Restart it and reload this page.');catalog=await a.json();sessionToken=(await b.json()).sessionToken;}
 el('recording').replaceChildren(...catalog.recordings.map(r=>{const option=node('option',r.title);option.value=r.id;return option;}));const selected=new URLSearchParams(location.search).get('case');if(catalog.recordings.some(x=>x.id===selected))el('recording').value=selected;busyState(false,'Choose an example or import a token-recording-v1 file.');
 }catch(e){el('token-error').hidden=false;el('token-error').textContent=visible(e.message);el('token-status').textContent='Setup incomplete. Reload to retry.';}})();
