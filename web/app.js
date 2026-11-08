'use strict';
const $=id=>document.getElementById(id);
const visible=(value,json)=>String(value??'').replace(/[\\\p{Cc}\p{Bidi_Control}]/gu,c=>{
 if(json&&(c==='\\'||c<' '))return c;
 return c==='\\'?'\\\\':'\\u'+c.charCodeAt().toString(16).padStart(4,'0');
});
const attr=(node,name,value)=>node.setAttribute(name,value);
const setText=(id,value)=>$(id).textContent=visible(value);
const tabs=[...document.querySelectorAll('.tab')];
const panelFor=tab=>$('panel-'+tab.id.slice(4));
const status=$('inspection-status');
const nav=$('scenarios'),picker=$('case-select');
const evidence=$('evidence-list'),raw=$('raw'),find=$('raw-find'),match=$('raw-match');
let catalog,selected,last,cache,bundle,facts,receiptRows,merchants,busy=false,retryInspection=false;
const params=new URLSearchParams(location.search);
const browserMode=params.get('browser')==='1';
let worker,pending,requestId=0;
let labCases=[],labCurrent=null,labReduction=null;
function resetWorker(message){
 const job=pending;
 worker?.terminate();
 worker=pending=null;
 if(job){clearTimeout(job.timer);job.reject(Error(message));}
}
function browserRequest(path,body){
 if(pending)throw Error('Inspection running');
 if(!worker){
  worker=new Worker('browser-worker.js?bundle=lab-v5');
  worker.onmessage=({data:{id,progress,error,result}})=>{
   const job=pending;
   if(!job||id!==job.id)return;
   if(progress)return setBusy(progress);
   if(error!==undefined)return resetWorker(error);
   pending=null;
   clearTimeout(job.timer);
   if(result?.error!==undefined)job.reject(Error(result.error,{cause:400}));
   else job.resolve(result);
  };
  worker.onerror=()=>resetWorker('Python failed. Use ZIP.');
 }
 return new Promise((resolve,reject)=>{
  const id=++requestId;
  const timer=setTimeout(()=>resetWorker('Browser timeout. Use ZIP.'),path==='/api/catalog'?90000:30000);
  pending={id,timer,resolve,reject};
  try{worker.postMessage({id,path,body});}
  catch(error){resetWorker(error.message);}
 });
}
if(browserMode){document.querySelector('.local-status').textContent='Browser replay';$('browser-note').hidden=false;}
const esc=(x,json)=>visible(x,json).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function formatYocto(value){
 const digits=value.padStart(25,'0');
 return (digits.slice(0,-24)+'.'+digits.slice(-24)).replace(/\.?0+$/,'');
}
const fitsYocto=(value,digits,bits)=>isText(value)&&value.length<=digits
 &&/^(0|[1-9]\d*)$/.test(value)&&(value.length<digits||BigInt(value)<2n**bits);
function near(value){
 if(value==null)return 'unknown';
 if(!fitsYocto(value,78,256n))throw Error('Invalid NEAR amount field.');
 return formatYocto(value);
}
const inNear=value=>near(value)+' NEAR';
const pretty=x=>JSON.stringify(x,null,2);
const reportJson=()=>cache ??= pretty(last);
const definitionRows=fields=>fields.map(([label,value,ref])=>`<dt>${esc(label)}</dt><dd>${esc(value)}${sourceHtml(ref)}</dd>`).join('');

const isPrincipal=f=>f.role==='ordinary_principal';
const positivePrincipal=f=>isPrincipal(f)&&/^[1-9]\d*$/.test(f.requested_yocto);
const amount=(value, excess='')=>`<span class="amount-figure${excess?' breached':''}">${near(value)}</span><span class="amount-unit">NEAR</span>${excess}`;
const policyLabels={within:'Within scope',breached:'Limit exceeded',unknown:'Unresolved',unsupported:'Unsupported',conflict:'Evidence conflict'};
function intentRow(c,[count=0,rank=0]=[],hasReceipt){
 const outputLabel=!count?'Not required':rank===4?'Failed':rank?'Unknown':'Passed';
 const state=count?outputLabel.toLowerCase():'not-declared';
 const known=c.exact_total!=null;
 const excess=c.lower_excess;
 const extra=excess!=null&&excess!=='0'?`<span class="cell-note breached">${known?'':'At least '}${inNear(excess)} over the limit</span>`:'';
 const committed=known?amount(c.exact_total,extra):`<span class="amount-unresolved">Unknown</span><span class="cell-note">Known subtotal: ${inNear(c.known_subtotal)}</span>${extra}`;
 const id=esc(c.intent);
 const intent=hasReceipt
  ?`<button class="intent-id" aria-label="Payment receipts for intent ${id}">${id} →</button>`
  :`<span class="intent-id">${id}</span>`;
 return `<tr><th scope="row">${intent}<span class="policy-state ${c.status}">${policyLabels[c.status]}</span></th><td>${amount(c.cap)}</td><td>${committed}</td><td><span class="output-state ${state}">${outputLabel}</span>${count?`<span class="cell-note">${count} output${count===1?'':'s'}</span>`:''}</td></tr>`;
}
function intentLedger(merchants,byIntent,facts){
 if(!merchants.length)return '<p class="empty">No principal limits.</p>';
 const withReceipts=new Set(facts.filter(isPrincipal).map(f=>f.intent));
 const rows=merchants.map(c=>intentRow(c,byIntent.get(c.intent),withReceipts.has(c.intent))).join('');
 return reportTable('<caption class="sr-only">Payment and output by intent.</caption>',
  ['Intent','Allowed','Committed','Useful output<small>Against reference</small>'],rows);
}
function reportTable(caption,headers,rows){
 return `<table>${caption}<thead><tr>${headers.map(text=>`<th scope="col">${text}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`;
}

function recoveryFinding(report){
 const row=report.constraints.find(c=>c.metric==='principal_recovery'&&c.status==='breached');
 if(!row)return null;
 const forbidden=row.parents.find(p=>p.forbidden_refund_facts.length);
 if(forbidden){
  return {tone:'exception',intent:row.intent,label:'refund destination breach',total:'Wrong recipient',
   caption:'Disallowed refund recipient.',refs:forbidden.forbidden_refund_facts};
 }
 const failed=row.parents.find(p=>p.failed_refund_facts.length&&p.expected_yocto!=null
  &&p.finalized&&p.expected_yocto!==p.successful_allowed_yocto);
 return failed&&{tone:'breach',intent:row.intent,label:'principal recovery failed',
  total:near(failed.successful_allowed_yocto),unit:true,
  caption:'Recovered to allowed recipients · '+inNear(failed.expected_yocto)+' required',
  refs:failed.failed_refund_facts};
}

function renderFinding(merchants, failedOutputs, report){
 const row=merchants.find(c=>c.status==='breached')
  ??merchants.find(c=>c.intent===failedOutputs[0]?.intent)
  ??merchants.find(c=>c.exact_total==null)
  ??merchants.find(c=>c.exact_total!=='0')
  ??merchants[0];
 const failed=row?failedOutputs.find(u=>u.intent===row.intent):failedOutputs[0];
 const otherBreach=row?.status!=='breached'&&report.constraints.find(c=>c.status==='breached');
 let view=otherBreach&&(recoveryFinding(report)??{
  tone:'exception',intent:otherBreach.intent,label:otherBreach.metric.replaceAll('_',' '),
  total:'Policy breach',caption:'See the constraint below.',refs:otherBreach.witnesses
 });
 if(!view&&row){
  const exact=row.exact_total!=null;
  const breached=row.status==='breached';
  const quantity=row.exact_total??row.known_subtotal;
  const tiny=quantity!=null&&row.cap!=null&&BigInt(quantity)<1000000n&&BigInt(row.cap)<1000000n&&(quantity!=='0'||row.cap!=='0');
  const unit=tiny?'yoctoNEAR':'NEAR',number=value=>tiny?value:near(value),amount=value=>number(value)+' '+unit;
  const cap=row.cap==null?'Limit unknown':amount(row.cap)+' allowed';
  const label=breached?'payment limit exceeded':failed?'required output failed':exact?'native principal':'payment unresolved';
  view={tone:breached?'breach':!exact?'unknown':failed?'output':'measured',
   intent:row.intent,label,unit:(exact||breached)&&unit,
   total:exact?number(row.exact_total):breached?'≥'+number(row.known_subtotal):'Unknown',
   caption:(exact?'Committed principal':breached?'Exact total unknown':'Known subtotal '+amount(row.known_subtotal))+' · '+cap,
   committed:row.exact_total,limit:row.cap,output:breached?undefined:failed,
   refs:row.witnesses.length?row.witnesses:report.native_facts.filter(f=>f.intent===row.intent
    &&positivePrincipal(f)).map(f=>f.id)};
 }
 if(!view&&failed){
  view={tone:'exception',intent:failed.intent,label:'required output failed',total:'Output failed',
   caption:'Output check failed.',output:failed};
 }
 const finding=$('finding');
 finding.hidden=!view;
 if(!view)return;

 finding.dataset.tone=view.tone;
 setText('finding-label',`Intent ${view.intent} · ${view.label}`);
 setText('finding-total',view.total);
 $('finding-unit').hidden=!view.unit;
 setText('finding-unit',typeof view.unit==='string'?view.unit:'NEAR');
 const proof=$('finding-proof');
 const output=report.utility.required.indexOf(view.output);
 const refs=new Set(view.refs);
 const count=refs.size?report.native_facts.filter(f=>refs.has(f.id)).length:0;
 setText('finding-caption',view.caption+(count<refs.size?' · Witness rows unavailable':''));
 proof.hidden=output<0&&!count;
 proof.textContent=output>=0?'Review recorded output':'Review '+count+' linked action'+(count===1?'':'s');
 proof.onclick=()=>{
  if(busy||finding.hidden||proof.hidden)return;
  if(output<0)showEvidence(refs);
  else focusResult($('utility-'+output),'overview');
 };
 renderFindingScale(view.committed,view.limit);
}

function renderFindingScale(total,cap){
 const scale=$('finding-scale');
 scale.hidden=total==null||cap==null||total==='0'&&cap==='0';
 if(scale.hidden)return;
 const committed=BigInt(total),allowed=BigInt(cap);
 const breached=committed>allowed;
 const max=breached?committed:allowed;
 const width=value=>Number(value*1000n/max);
 const capWidth=width(allowed),fill=breached?capWidth:width(committed);
 const capMark=Math.min(998,Math.max(2,capWidth));
 attr($('finding-fill'),'d',`M0 2H${fill}v8H0Z`);
 attr($('finding-excess'),'d',`M${capWidth} 4H1000v4H${capWidth}Z`);
 $('finding-over-key').hidden=!breached;
 attr($('finding-cap'),'d','M '+capMark+' 0 V 12');
}

function focusResult(target,tab){
 if(tab)setTab(tab);
 target?.focus({preventScroll:true});
 target?.scrollIntoView({behavior:'instant'});
}
function setEvidenceOrigin(origin){
 const back=$('evidence-back');
 back.href=origin?'#intents':'#finding';
 back.textContent=origin?'Back to payment row':'Back to finding';
 back.onclick=event=>{
  event.preventDefault();
  focusResult(origin??$('finding'),origin&&'overview');
 };
}
function showEvidence(refs,origin=null){
 setEvidenceOrigin(origin);
 setTab('evidence');
 let first,next=null;
 for(let i=receiptRows.length;i--;){
  const row=receiptRows[i],wasLinked=row.classList.contains('linked-fact');
  if(row.classList.toggle('linked-fact',refs.has(facts[i].id))){
   evidence.prepend(row);
   first=row;
  }else{
   if(wasLinked&&row.nextElementSibling!==next)evidence.insertBefore(row,next);
   next=row;
  }
 }
 if(first)first.open=true;
 focusResult(first?.firstElementChild??$('tab-evidence'));
}
function receiptOutcome({execution_state:state,finality,committed_yocto}){
 if(state==='unsupported')return 'Unsupported action';
 if(state==='unfinalized'||finality!=='whole_final'&&finality!=='bound_final_head')return 'Finality unknown';
 if(state==='committed')return evidenceAmount(committed_yocto);
 return state==='rolled_back'?'Rolled back':'Outcome unknown';
}
function evidenceAmount(value){
 return fitsYocto(value,39,128n)
  ?formatYocto(value)+' NEAR':'Amount unavailable';
}
function renderEvidence(report){
 const principal=[],other=[];
 for(const fact of report.native_facts)(positivePrincipal(fact)?principal:other).push(fact);
 facts=principal.concat(other);
 evidence.innerHTML=facts.map((fact,i)=>{
  const intent=fact.intent==null?'Ancillary':'Intent '+esc(fact.intent);
  const role={ordinary_principal:'Principal',principal_refund:'Principal refund',gas_return:'Gas return'}[fact.role]??'Unclassified';
  const amount=receiptOutcome(fact);
  return `<details class="fact" data-row="${i+1}"><summary><span><strong>Row ${i+1} · ${intent}</strong>${esc(fact.from)} → ${esc(fact.to)}</span><span><strong>${role}</strong>${amount}</span></summary></details>`;
 }).join('');
 receiptRows=[...evidence.children];
}

const isCount=n=>Number.isSafeInteger(n)&&n>=0;
const isText=value=>typeof value==='string'&&!!value;
const isSha256=value=>isText(value)&&/^[0-9a-f]{64}$/.test(value);
function isSourceRef(ref){
 const {source,pointer}=ref??{};
 return isText(source)&&typeof pointer==='string'&&!/^[^/]|~(?![01])/.test(pointer);
}
function sourceBinding(ref,sources){
 if(!isSourceRef(ref))return null;
 const digest=Object.hasOwn(sources,ref.source)&&sources[ref.source]?.sha256;
 return isSha256(digest)?[ref.source,digest]:null;
}

evidence.addEventListener('toggle',({target})=>{
 if(!target.open||target.children.length>1)return;
 const fact=facts?.[target.dataset.row-1];
 if(!fact)return;
 const {id,action_index,action_ref,outcome_ref}=fact;
 const {scope:{run_id},sources}=last.report;
 const hashes=[action_ref,outcome_ref].map(ref=>sourceBinding(ref,sources));
 const fields=[
  ['Intent / role',(fact.intent??'—')+' / '+fact.role],
  ['Execution',fact.execution_state+' · '+fact.finality],
  ['Tx hash',fact.tx_hash],
  ['Receipt',fact.receipt_id],
  ['Requested',evidenceAmount(fact.requested_yocto)],
  ['Action index',action_index+' / '+fact.action_type],
  fact.provenance==='derived_initial'?['Source','From transaction',hashes[0]&&action_ref]:['Source',fact.provenance]
 ];
 const json=isText(run_id)&&isText(id)&&isCount(action_index)&&hashes.every(Boolean)
  ?pretty({
  format:'agent-crash-lab/citation-v1',run_id,fact_id:id,action_index,core_sha256:last.execution.coreSha256,
  sources:Object.fromEntries(hashes),action_ref,outcome_ref
 }):'';
 const citation=json?`<button>Save citation</button><pre>${esc(json,true)}</pre>`
  :'<p class="empty" role="status">Citation needs a complete reference.</p>';
 target.insertAdjacentHTML('beforeend',`<dl class="fact-meta">${definitionRows(fields)}</dl>${citation}`);
 if(json)target.querySelector('button').onclick=()=>{if(!busy)download('citation-'+target.dataset.row,json);};
},true);

const page=document.documentElement.dataset,themeKey='crash-lab-theme';
function applyTheme(light){
 page.theme=light?'light':'dark';
 setText('theme-toggle',light?'Use dark theme':'Use light theme');
}
let savedTheme;
try{savedTheme=localStorage.getItem(themeKey);}catch{}
applyTheme(savedTheme==='light');
$('theme-toggle').onclick=()=>{
 applyTheme(page.theme==='dark');
 try{localStorage.setItem(themeKey,page.theme);}catch{}
};

async function request(path,body,refresh=true){
 if(browserMode)return browserRequest(path,body);
 const options = {signal: AbortSignal.timeout(30000)};
 if (body !== undefined) Object.assign(options, {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-CrashLab-Token': catalog.sessionToken},
  body: path === '/api/assess' ? body : JSON.stringify(body)
 });
 const r = await fetch(path, options);
 const data=await r.json().catch(invalidReport);
 if(r.ok)return data;
 if(refresh&&body&&r.status===403&&data?.error==='Local session token required'){
  const token=(await request('/api/catalog'))?.sessionToken;
  if(isText(token)){
   catalog.sessionToken=token;
   return request(path,body,false);
  }
 }
 throw Error(data?.error||`HTTP ${r.status}`,{cause:r.status});
}
function downloadNamed(filename, payload) {
 const url = URL.createObjectURL(new Blob([payload], {type: 'application/json'}));
 const link = document.createElement('a');
 link.href = url;
 link.download = filename;
 link.click();
 setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function download(name,payload){downloadNamed(`crash-lab-${selected?.id ?? bundle.key}-${name}.json`,payload);}
function setBusy(message=''){
 busy=!!message;
 document.querySelectorAll('#lab-panel input').forEach(input=>input.disabled=busy);
 document.querySelectorAll('#lab-cases-list button').forEach(control=>attr(control,'aria-disabled',busy));
 attr($('main'),'aria-busy',busy);
 $('run').textContent=message||(catalog?(!bundle&&!selected?'Import corrected bundle':(retryInspection?'Retry':'Run')+' inspection'):'Retry setup');
 $('upload').disabled=!catalog;
 document.querySelectorAll('.sidebar :is(button,input,select),main button[id]:not(.tab,#finding-proof)').forEach(control=>attr(control,'aria-disabled',busy));
 if(busy){
  $('error').hidden=true;
  status.textContent=message;
 }
}
function error(e,hint=''){status.textContent='';$('error').hidden=false;setText('error',(e.message||String(e))+hint);}
function showCase(s,filename){
 if($('main').getBoundingClientRect().top<0)scrollTo({top:0,behavior:'instant'});
 selected=s;
 const id=s?.id??'',url=new URL(location.href);
 if(s)url.searchParams.set('case',id);
 else url.searchParams.delete('case');
 url.hash='';
 if(url.href!==location.href)history.replaceState(history.state,'',url);
 const view=s??{title:'Imported recording',description:filename,question:'Check this bundle.'};
 for(const key of ['title','description','question'])setText(key,view[key]);
 setText('scenario-kind',s?caseOrigin(s.kind):view.title);
 setText('scenario-number',s?'Case '+(catalog.scenarios.indexOf(s)+1):'Custom case');
 picker.value=id;
 for(const b of nav.children){
  const current=b.dataset.id===id;
  attr(b,'aria-current',current);
  if(current)nav.scrollTop=Math.min(b.offsetTop,Math.max(nav.scrollTop,b.offsetTop+b.offsetHeight-nav.clientHeight));
 }
 setTab('overview');
}
const findCase=id=>catalog?.scenarios.find(s=>s.id===id);
const caseOrigin=kind=>({synthetic:'Synthetic mutation','live-model':'Recorded Qwen · owned sandbox','model-proposals':'Recorded Qwen · synthetic payments'}[kind]??'Owned sandbox');
nav.onclick=({target})=>{
 const button=target.closest('.scenario');
 if(button)select(findCase(button.dataset.id));
};
function select(s){
 if(busy||!s){picker.value=selected?.id??'';return;}
 clearLabContext();
 bundle=null;
 showCase(s);
 run();
}
const highlights=CSS.highlights;
let matchEnd=0,placement;
const clearMatch=()=>{cancelAnimationFrame(placement);highlights?.delete(raw.id);};
find.oninput=find.onreset=()=>{matchEnd=0;match.value='';clearMatch();};
find.onsubmit=event=>{
 event.preventDefault();
 const text=raw.textContent, term=visible(find.elements.query.value,true), selection=getSelection();
 let start=text.indexOf(term,matchEnd);
 if(start<0)start=text.indexOf(term);
 selection.removeAllRanges();
 clearMatch();
 if(!term||start<0){match.value='Not found';return;}
 let end=matchEnd=start+term.length;
 const range=new Range();
 for(const child of raw.childNodes){
  const node=child.firstChild??child;
  if(start>=0&&start<node.length)range.setStart(node,start);
  if(end<=node.length){range.setEnd(node,end);break;}
  start-=node.length;
  end-=node.length;
 }
 const long=highlights&&term.length>65536;
 match.value='Match found';
 const result=range.cloneRange();
 if(long)highlights.set(raw.id,new Highlight(result));
 else selection.addRange(result);
 range.collapse(true);
 placement=requestAnimationFrame(()=>{
  if(!raw.offsetHeight)return;
  const {offsetTop=0,height=innerHeight}=window.visualViewport??{};
  const viewBottom=offsetTop+height,zoom=raw.currentCSSZoom??1;
  const formTop=find.getBoundingClientRect().top-offsetTop;
  const missing=raw.getBoundingClientRect().top+Math.min(height,40*zoom)-viewBottom;
  scrollBy({top:Math.max(Math.min(formTop,0),missing),behavior:'instant'});
  const box=raw.getBoundingClientRect(),head=range.getBoundingClientRect();
  const middle=(Math.max(offsetTop,box.top)+Math.min(viewBottom,box.bottom))/2;
  raw.scrollTop+=(head.top+head.height/2-middle)/zoom;
 });
};
function renderRaw(text){
 text=visible(text,true);
 if(text.length<=65536){
  raw.textContent=text;
  return;
 }
 // Prefer line or separator breaks within a 16K code point cap.
 for(const part of text.match(/.{8191,16383}\n|.{8191,16383}[ /.,](?![\p{M}\u200d])|.{1,16384}/gsu)){
  const segment=document.createElement('span');
  segment.textContent=part;
  raw.append(segment);
 }
}
function renderActivePanel(){
 if(!last)return;
 const report=last.report;
 if(!$('panel-raw').hidden&&!raw.firstChild)renderRaw(reportJson());
 if(!$('panel-scope').hidden&&!$('scope-facts').firstChild)renderScope(report);
 if(!facts&&!$('panel-evidence').hidden&&report.invocation.status==='assessed')renderEvidence(report);
}
function setTab(id){
 tabs.forEach(b=>{
  const active=b.id==='tab-'+id;
  attr(b,'aria-selected',active);
  b.tabIndex=active?0:-1;
  panelFor(b).hidden=!active;
 });
 renderActivePanel();
}
function clearResults(){
 last=cache=facts=receiptRows=merchants=null;
 $('results').hidden=true;
 find.reset();
 for(const id of ['raw','evidence-list','scope-facts','intents','utility-list','constraint-list','verdicts'])$(id).replaceChildren();
 $('finding').hidden=true;
 setEvidenceOrigin(null);
}
async function run(){
 if(busy||!bundle&&!selected)return;
 setBusy('Inspecting…');
 clearResults();
 try{
  last=await request(bundle?'/api/assess':'/api/run',bundle?.bytes??{id:selected.id});
  status.textContent=render(last);
  if(labCurrent&&sameJSON(projectLabReport(last.report))!==sameJSON(labCurrent.actual))throw Error('Generated input/report disagreement. No finding certified.');
  renderCI();
  renderActivePanel();
  $('results').hidden=false;
 }catch(e){
  clearResults();
  clearLabContext();
  const invalidBundle=!!bundle&&e.cause===400;
  if(invalidBundle)bundle=null;
  retryInspection=!invalidBundle;
  error(e,invalidBundle&&!e.message.includes('Import ')?' · Import a corrected bundle.':'');
 }finally{setBusy();}
}
function verdicts(inspection,...cards){
 const titles=['Payment authority','Useful work','Payment evidence'];
 const defaults=['Principal by intent','Reference check'];
 $('verdicts').innerHTML=cards.map(([state,value,note,foot],i)=>
  `<article class="verdict ${state}"><div class="card-kicker">${titles[i]}</div><div class="verdict-value">${esc(value)}</div><p>${esc(note)}</p><div class="card-foot">${foot??defaults[i]}</div></article>`
 ).join('');
 return `${inspection}. ${cards[0][1]}. ${cards[1][1]}.`;
}

function excerpt(text) {
 if (text.length <= 160) return text;
 const preview = text.match(/^.{1,160}/su)[0];
 return preview === text ? text : preview + '… See Raw report.';
}
const label = (text, invalid = 'Invalid ID') =>
 typeof text === 'string' ? excerpt(text) : invalid;
const joined=parts=>parts.filter(Boolean).join(' · ');
function sourceHtml(ref,caption=''){
 if(ref==null)return caption?'<div>No pointer</div>':'';
 if(!isSourceRef(ref))return '<div>Invalid reference</div>';
 const path=esc(ref.source+' · '+(ref.pointer||'(root)'));
 return ref.pointer.length>160
  ?`<details><summary>${caption||'Source path'}</summary>${path}</details>`
  :`<div>${caption&&caption+' · '}${path}</div>`;
}
function renderScope(r){
 const fields=[['Engine SHA256',last.execution.coreSha256]];
 if(r.invocation.status==='assessed'){
  const {run_id,chain_id,protocol_version,capture}=r.scope;
  const text=(value,valid=isText)=>valid(value)?value:'Unavailable';
  fields.push(['Run ID',text(run_id)],['Network / protocol version',text(chain_id)+' / '+text(protocol_version,isCount)],
   ['Authority',r.authority.kind],sourceBinding(capture,r.sources)?['Capture','',capture]:['Capture','Unavailable']);
  for(const d of r.diagnostics)fields.push([d.id+' · '+d.scope,d.message,d.ref]);
 }else fields.push([r.invocation.code,r.invocation.message]);
 $('scope-facts').innerHTML=definitionRows(fields);
}

const invalidReport=()=>{throw Error('The result contains invalid data. Please try again.');};
// Report contract: validate before creating any verdict or deferred evidence panel.
// This checks the evaluator's display contract, not signatures or capture authenticity.
function validateInspection(data){
 const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
 const text=value=>typeof value==='string'&&value.length>0;
 const count=value=>Number.isSafeInteger(value)&&value>=0;
 const sha=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
 const boolean=value=>typeof value==='boolean';
 const own=(value,key)=>Object.hasOwn(value,key);
 const require=(condition,path)=>{
  if(!condition)throw Error('The result contains invalid data. Please try again.',{cause:'report-contract: '+path});
 };
 const strings=value=>Array.isArray(value)&&value.every(text);
 const unique=value=>new Set(value).size===value.length;
 const amount=(value,nullable=false,bits=256n)=>nullable&&value===null
  ||typeof value==='string'&&value.length<=78&&/^(0|[1-9]\d*)$/.test(value)&&BigInt(value)<2n**bits;
 require(object(data)&&object(data.report)&&object(data.execution),'response');
 const r=data.report,e=data.execution;
 require(text(e.coreVersion)&&sha(e.coreSha256)&&Number.isFinite(e.elapsedMs)&&e.elapsedMs>=0,'execution');
 require(['actual-local-assessment','actual-browser-python-assessment'].includes(e.mode)
  &&e.liveModel===false&&e.networkTransactions===0,'execution scope');
 require(r.format==='agent-crash-lab/report-v1'&&object(r.invocation),'report format');
 const invocation=r.invocation.status;
 require(['assessed','rejected','failed'].includes(invocation),'invocation');
 if(invocation!=='assessed'){
  require(text(r.invocation.code)&&text(r.invocation.message),'unassessed explanation');
  require(!['constraints','native_facts','utility','coverage'].some(key=>own(r,key)),'unassessed verdict');
  return data;
 }
 require(r.invocation.version===e.coreVersion&&r.invocation.profile==='near-sandbox-2.14/native-v1','assessed profile');
 require(object(r.authority)&&['historical_controlled','reconstructed','counterfactual'].includes(r.authority.kind)
  &&Array.isArray(r.authority.basis)&&text(r.authority.note),'authority');
 require(object(r.scope)&&text(r.scope.run_id)&&text(r.scope.chain_id)&&count(r.scope.protocol_version)
  &&boolean(r.scope.closed_horizon)&&text(r.scope.horizon_note),'scope');
 require(object(r.sources)&&Object.keys(r.sources).length>0,'sources');
 for(const [id,source] of Object.entries(r.sources)){
  require(/^[A-Za-z0-9_.-]{1,64}$/.test(id)&&object(source)&&sha(source.sha256)&&count(source.bytes),'source binding');
 }
 const sourceRef=ref=>object(ref)&&text(ref.source)&&own(r.sources,ref.source)
  &&typeof ref.pointer==='string'&&!/^[^/]|~(?![01])/.test(ref.pointer);
 require(sourceRef(r.scope.capture)&&r.authority.basis.every(sourceRef),'authority references');
 require(['constraints','native_facts','diagnostics'].every(key=>Array.isArray(r[key])),'report collections');
 require(object(r.utility)&&Array.isArray(r.utility.required)&&Array.isArray(r.utility.intermediate),'utility collections');
 const inventory=r.inventory,coverage=r.coverage;
 require(object(inventory)&&object(coverage),'inventory and coverage');
 for(const key of ['rpc_records','send_observations','declared_attempts','observed_transaction_hashes',
  'selected_required_utility','selected_intermediate_utility'])require(count(inventory[key]),'inventory '+key);
 require(inventory.observed_transaction_hashes<=inventory.rpc_records
  &&inventory.send_observations<=inventory.rpc_records
  &&(inventory.utility_observations===null||count(inventory.utility_observations)),'inventory bounds');
 require(inventory.selected_required_utility===r.utility.required.length
  &&inventory.selected_intermediate_utility===r.utility.intermediate.length,'utility counts');
 require(boolean(coverage.financial_scope_complete)&&boolean(coverage.all_required_utility_assessed)
  &&text(coverage.trust),'coverage');
 require(!coverage.financial_scope_complete||r.scope.closed_horizon,'closed financial scope');
 const diagnostics=new Set();
 for(const d of r.diagnostics){
  require(object(d)&&[d.id,d.category,d.scope,d.message].every(text)&&!diagnostics.has(d.id),'diagnostic');
  diagnostics.add(d.id);
 }
 const reasons=(row,required=false)=>{
  const ids=own(row,'diagnostic_ids')?row.diagnostic_ids:[];
  require(strings(ids)&&ids.every(id=>diagnostics.has(id))&&(!required||ids.length>0),'diagnostic references');
 };
 const facts=new Map();
 for(const f of r.native_facts){
  require(object(f)&&[f.id,f.attempt_id,f.tx_hash,f.receipt_id,f.action_type,f.from,f.to].every(text)
   &&!facts.has(f.id)&&count(f.action_index),'native action identity');
  require(f.intent===null||text(f.intent),'native action intent');
  require(['ordinary_principal','principal_refund','gas_return','unclassified_system_or_unsupported_origin'].includes(f.role)
   &&['committed','rolled_back','unfinalized','unknown','unsupported'].includes(f.execution_state)
   &&['whole_final','bound_final_head','unresolved'].includes(f.finality)
   &&['observed','derived_initial'].includes(f.provenance),'native action state');
  require(boolean(f.self)&&f.self===(f.from===f.to),'self transfer');
  require(amount(f.requested_yocto,true,128n)&&amount(f.committed_yocto,true,128n),'native amounts');
  if(f.execution_state==='committed')require(f.requested_yocto!==null&&f.requested_yocto===f.committed_yocto,'committed amount');
  else require(f.committed_yocto===(f.execution_state==='rolled_back'?'0':null),'uncommitted amount');
  require(!['committed','rolled_back'].includes(f.execution_state)||f.finality!=='unresolved','action finality');
  // Missing citations stay visible as unavailable; they cannot create a signed-history claim.
  require(own(f,'action_ref')&&own(f,'outcome_ref'),'action references');
  facts.set(f.id,f);
 }
 const witnesses=(ids,intent)=>{
  require(strings(ids)&&unique(ids)&&ids.every(id=>facts.has(id)&&facts.get(id).intent===intent),'fact references');
  return ids.map(id=>facts.get(id));
 };
 const constraints=new Set();
 for(const c of r.constraints){
  require(object(c)&&['within','breached','unknown','unsupported','conflict'].includes(c.status)&&boolean(c.complete),'constraint');
  reasons(c);
  // A malformed owner declaration is a genuine unknown result, not a malformed report.
  if(!own(c,'metric')){
   require(c.status==='unknown'&&!c.complete,'invalid owner constraint');
   reasons(c,true);
   continue;
  }
  require(text(c.id)&&text(c.intent)&&!constraints.has(c.id),'constraint identity');
  require(text(c.unit),'constraint unit');
  constraints.add(c.id);
  const linked=witnesses(c.witnesses,c.intent);
  if(['merchant_gross_principal','protected_external_disbursement','committed_settlement_attempts'].includes(c.metric)){
   require(['cap','known_subtotal','lower_excess'].every(key=>amount(c[key]))
    &&amount(c.exact_total,true)&&amount(c.exact_excess,true),'constraint amounts');
   const cap=BigInt(c.cap),subtotal=BigInt(c.known_subtotal),excess=subtotal>cap?subtotal-cap:0n;
   require(BigInt(c.lower_excess)===excess,'constraint excess');
   require(c.exact_total===(c.complete?c.known_subtotal:null)
    &&c.exact_excess===(c.complete?c.lower_excess:null),'exact constraint totals');
   require(subtotal>cap?c.status==='breached':c.complete?c.status==='within'
    :['unknown','unsupported','conflict'].includes(c.status),'constraint verdict');
   require(linked.every(f=>f.role==='ordinary_principal'&&f.execution_state==='committed'
    &&BigInt(f.committed_yocto)>0n&&!f.self),'principal witnesses');
   const witnessed=c.metric==='committed_settlement_attempts'?BigInt(new Set(linked.map(f=>f.tx_hash)).size)
    :linked.reduce((sum,f)=>sum+BigInt(f.committed_yocto),0n);
   require(witnessed===subtotal,'witness subtotal');
  }else if(c.metric==='ordinary_recipient_allowlist'){
   require(strings(c.allowed_accounts)&&unique(c.allowed_accounts)&&strings(c.known_recipients)
    &&unique(c.known_recipients),'recipient lists');
   require(linked.every(f=>f.role==='ordinary_principal'&&f.execution_state==='committed'
    &&!c.allowed_accounts.includes(f.to)),'recipient witnesses');
   require(linked.length?c.status==='breached':c.complete?c.status==='within'
    :['unknown','unsupported','conflict'].includes(c.status),'recipient verdict');
  }else if(c.metric==='principal_recovery'){
   require(['destinations','full'].includes(c.mode)&&strings(c.allowed_accounts)
    &&unique(c.allowed_accounts)&&Array.isArray(c.parents),'recovery policy');
   let breached=false,missing=false;
   for(const parent of c.parents){
    require(object(parent)&&text(parent.receipt_id)&&text(parent.from)&&boolean(parent.finalized)
     &&amount(parent.expected_yocto,true)&&amount(parent.successful_allowed_yocto),'recovery parent');
    const refunds=witnesses(parent.refund_facts,c.intent);
    const failed=witnesses(parent.failed_refund_facts,c.intent);
    const forbidden=witnesses(parent.forbidden_refund_facts,c.intent);
    require(refunds.every(f=>f.role==='principal_refund'&&f.parent_receipt_id===parent.receipt_id),'refund parent');
    const equals=(rows,expected)=>rows.length===expected.length&&rows.every(f=>expected.includes(f));
    require(equals(failed,refunds.filter(f=>f.execution_state==='rolled_back'))
     &&equals(forbidden,refunds.filter(f=>f.execution_state==='committed'&&!c.allowed_accounts.includes(f.to))),'refund classification');
    const recovered=refunds.filter(f=>f.execution_state==='committed'&&c.allowed_accounts.includes(f.to))
     .reduce((sum,f)=>sum+BigInt(f.committed_yocto),0n);
    require(recovered===BigInt(parent.successful_allowed_yocto),'refund total');
    breached||=forbidden.length>0;
    if(parent.expected_yocto===null||!parent.finalized)missing=true;
    else if(c.mode==='full'&&BigInt(parent.expected_yocto)>0n&&parent.expected_yocto!==parent.successful_allowed_yocto){
     if(failed.length||forbidden.length)breached=true;
     else missing=true;
    }
   }
   require(breached?c.status==='breached':c.complete&&!missing?c.status==='within'
    :['unknown','unsupported','conflict'].includes(c.status),'recovery verdict');
  }else require(c.status==='unsupported'&&!c.complete,'unsupported constraint');
 }
 const checks=['status_check','context_check','content_check','answer_check'];
 // The core projects exact JSON quantities into decimal descriptors. Check
 // integrality without rounding, including decimal forms and negative zero.
 const quantity=value=>{
  if(typeof value==='number')return Number.isSafeInteger(value)&&value>=0;
  if(!object(value)||Object.keys(value).length!==1||!own(value,'exact_json_number'))return false;
  const n=value.exact_json_number;
  if(!object(n)||Object.keys(n).length!==3||![0,1].includes(n.sign)
   ||typeof n.digits!=='string'||n.digits.length>128||!/^\d+$/.test(n.digits)
   ||!Number.isSafeInteger(n.exponent)||Math.abs(n.exponent)>1024)return false;
  let units=BigInt(n.digits);
  if(n.sign&&units!==0n)return false;
  if(n.exponent<0){
   const divisor=10n**BigInt(-n.exponent);
   if(units%divisor!==0n)return false;
   units/=divisor;
  }else units*=10n**BigInt(n.exponent);
  return units<2n**64n;
 };
 const passedAnswer=answer=>object(answer)&&Object.keys(answer).length===2
  &&own(answer,'sku')&&text(answer.sku)&&own(answer,'units')&&quantity(answer.units);
 const assessedOutputs=new Set();
 for(const u of r.utility.required){
  require(object(u)&&['passed','failed','unknown','unsupported','invalid_reference'].includes(u.status),'required output');
  reasons(u);
  if(u.status!=='unknown'){
   require(text(u.id)&&text(u.intent)&&text(u.profile)&&!assessedOutputs.has(u.id),'output identity');
   assessedOutputs.add(u.id);
  }
  for(const key of checks)require(!own(u,key)||boolean(u[key]),'output check');
  for(const key of ['observed_status_present','observed_answer_present'])require(!own(u,key)||boolean(u[key]),'output presence');
  if(own(u,'observed_answer_present'))require(own(u,'observed_answer')
   &&(u.observed_answer_present||u.observed_answer===null),'recorded answer');
  if(own(u,'observed_status_present'))require(own(u,'observed_status')
   &&(u.observed_status_present||u.observed_status===null),'recorded HTTP status');
  if(own(u,'reference_check'))require(u.reference_check==='consistent','reference check');
  if(own(u,'response_sha256'))require(sha(u.response_sha256),'response digest');
  if(u.status==='passed')require(text(u.id)&&text(u.intent)&&u.profile==='inventory-gap-first-v1'&&sourceRef(u.observation_ref)
   &&u.reference_check==='consistent'&&u.observed_status_present&&u.observed_status===200
   &&u.observed_answer_present&&u.context_check===true&&u.content_check===true&&u.answer_check===true
   &&!checks.some(key=>u[key]===false)&&!u.diagnostic_ids?.length
   &&passedAnswer(u.observed_answer)&&sha(u.response_sha256),'passed output evidence');
  else if(u.status==='failed')require(checks.some(key=>u[key]===false)||u.diagnostic_ids?.length>0,'failed output evidence');
  else reasons(u,true);
 }
 for(const u of r.utility.intermediate){
  require(object(u)&&u.role==='permitted_intermediate'&&['observed','unknown'].includes(u.status)
   &&own(u,'ref'),'intermediate observation');
  reasons(u,u.status==='unknown');
  if(u.status==='observed')require(sourceRef(u.ref)&&boolean(u.observed_answer_present)
   &&own(u,'observed_status')&&own(u,'observed_answer')
   &&(u.observed_answer_present||u.observed_answer===null),'observed intermediate');
 }
 require(coverage.all_required_utility_assessed===r.utility.required.every(u=>['passed','failed'].includes(u.status)),'output coverage');
 return data;
}
// End report contract.
function render(data){
 validateInspection(data);
 const {report:r,execution}=data??{};
 const {status:outcome,code,message}=r?.invocation??{};
 const assessed=outcome==='assessed',failed=outcome==='failed';
 const state=assessed?'Inspection complete':failed?'Inspection failed':outcome==='rejected'?'Input rejected':'';
 const {rpc_records:rpcs,observed_transaction_hashes:txs,selected_required_utility:total,
  selected_intermediate_utility:permitted}=r?.inventory??{};
 const complete=r?.coverage?.financial_scope_complete;
 const {required:us,intermediate}=r?.utility??{};
 if(!state||r.format!=='agent-crash-lab/report-v1'||!isText(execution?.coreVersion)
  ||!Number.isFinite(execution.elapsedMs)||execution.elapsedMs<0||!isSha256(execution.coreSha256)
  ||(!assessed&&(!isText(code)||!isText(message)))
  ||(assessed&&(typeof complete!=='boolean'||![txs,rpcs].every(isCount)||txs>rpcs
   ||![r.constraints,r.native_facts,r.diagnostics,us,intermediate].every(Array.isArray)
   ||us.length!==total||intermediate.length!==permitted
   ||![r.scope,r.sources].every(v=>v&&typeof v==='object'&&!Array.isArray(v))
   ||!r.native_facts.every(f=>[f?.id,f?.from,f?.to].every(isText)))))
  invalidReport();
 const count=assessed?r.native_facts.length:0;
 setText('evidence-count',count);
 $('evidence-back').hidden=!count;
 setText('evidence-intro',count?'Linked first. Cite with bundle.':
  !assessed?state+'. See Raw report.':
  complete?'No action in scope.':'No verified actions.');
 setText('timing',`${execution.elapsedMs} ms · ${browserMode?'Wasm':'local'}`);
 setText('version',execution.coreVersion);
 retryInspection=failed;
 setText('run-state',state);
 if(!assessed)return verdicts(state,['unknown','Unassessed',message],['unknown','Not evaluated',''],
  ['unknown',code,failed?'Retry inspection.':'Import corrected bundle.','Raw report']);
 const cs=r.constraints;
 const messages=new Map(r.diagnostics.flatMap(d=>
  d&&[d.id,d.scope,d.message].every(isText)?[[d.id,d.message]]:[]));
 if(messages.size<r.diagnostics.length)invalidReport();
 const reasons=({diagnostic_ids:ids=[]})=>{
  if(!Array.isArray(ids))invalidReport();
  return joined(ids.map(id=>messages.get(id)??invalidReport()).slice(0,2));
 };
 for(const row of intermediate){
  if(row?.role!=='permitted_intermediate')invalidReport();
  reasons(row);
 }
 let breaches=0,uncertain=0;
 $('constraint-list').innerHTML=cs.map(c=>{
  const status=c?.status;
  if(!isText(status)||!Object.hasOwn(policyLabels,status))invalidReport();
  if(status==='breached')breaches++;
  else if(status!=='within')uncertain++;
  return `<div class="constraint-row"><div>${esc(label(c.id))}<div class="constraint-detail">${esc(joined([label(c.metric??'','Invalid metric'),c.unit||'policy',reasons(c)]))}</div></div><span class="row-state ${status}">${status}</span></div>`;
 }).join('');
 const checks={status:'HTTP status',context:'Context',content:'Document',answer:'Answer'};
 const states=['passed','unknown','unsupported','invalid_reference','failed'];
 const bad=[],byIntent=new Map();
 let passed=0,unresolved=-1;
 const outputRows=us.map((u,index)=>{
  const {status,observed_answer_present:present}=u??{};
  const rank=states.indexOf(status);
  if(rank<0)invalidReport();
  if(!rank)passed++;
  else if(rank===4)bad.push(u);
  else if(unresolved<0)unresolved=index;
  const [count=0,prior=0]=byIntent.get(u.intent)??[];
  byIntent.set(u.intent,[count+1,Math.max(rank,prior)]);
  if(present!==undefined&&typeof present!=='boolean'||!rank&&!present
   ||present&&!Object.hasOwn(u,'observed_answer'))invalidReport();
  const answer=present?'Answer: '+excerpt(JSON.stringify(u.observed_answer))
   :present===false?'No recorded answer':'Answer not verified';
  const reason=reasons(u);
  const evidence=!rank?'':`<div>${esc(joined(Object.keys(checks).map(k=>u[k+'_check']===false
   &&(k!=='answer'||present!==false)&&checks[k]+' mismatch').concat(reason)))}</div>${sourceHtml(u.observation_ref,u.reference_check?'':'Unverified source')}`;
  return `<div id="utility-${index}" class="utility-row" tabindex="-1"><div>Intent ${esc(u.intent??'—')} · ${esc(label(u.id))}<div class="utility-answer">${esc(answer,true)}${evidence}</div></div><span class="status ${status}">${status.replace('_',' ')}</span></div>`;
 }).join('');
 const unknown=total-passed-bad.length;
 if(r.coverage.all_required_utility_assessed!==!unknown)invalidReport();
 const payment=!cs.length?['none','Not declared','No limits set.']
  :breaches||uncertain?[breaches?'breach':'unknown',breaches?'Policy breached':'Evidence incomplete',
   joined(['Checks',breaches&&breaches+' breached',uncertain&&uncertain+' unresolved'])+'.']
  :['good','Within declared limits','No breach observed.'];
 const output=!total?['none','Not required']:bad.length?['breach','Output failed']
  :unknown?['unknown','Output unknown']:['good','Useful work verified'];
 output.push(!total?'No required output.':`${passed} / ${total} required outputs passed${bad.length?`; ${bad.length} failed`:''}${unknown?`; ${unknown} unknown`:''}.`);
 if(breaches&&passed&&passed===total)payment[2]+=' Useful work cannot authorize extra spending.';
 if(!breaches&&bad.length)output[2]+=' Payment cannot verify output.';
 if(cs.length&&!breaches&&!bad.length&&(uncertain||!complete))payment[2]+=' Unknown does not imply zero.';
 if(unknown)output[3]='<button id="review-output">Review unresolved output</button>';
 const announcement=verdicts(state,payment,output,[complete?'':'unknown',complete?'Scoped evidence complete':'Evidence incomplete',`${txs} transaction hashes · ${rpcs} RPC capture records. Origin assumed.`,selected?caseOrigin(selected.kind):r.authority.kind==='counterfactual'?'Declared synthetic':'Import origin unverified']);
 if(unknown)$('review-output').onclick=()=>{
  if(!busy)focusResult($('utility-'+unresolved),'overview');
 };
 merchants=cs.filter(c=>c.metric==='merchant_gross_principal');
 renderFinding(merchants,bad,r);$('intents').innerHTML=intentLedger(merchants,byIntent,r.native_facts);
 $('utility-list').innerHTML=(outputRows||'<div class="empty">No required outputs.</div>')+
  (permitted?`<div class="empty">${permitted} permitted intermediate observations.</div>`:'');
 return announcement;
}
$('run').onclick=()=>catalog?(!bundle&&!selected?$('upload').click():run()):start();
$('intents').onclick=({target})=>{
 const button=target.closest('button.intent-id');
 if(busy||!button)return;
 const {intent}=merchants[button.closest('tr').sectionRowIndex];
 const refs=last.report.native_facts.filter(f=>f.intent===intent&&isPrincipal(f)).map(f=>f.id);
 showEvidence(new Set(refs),button);
};
picker.onchange=event=>select(findCase(event.currentTarget.value));
tabs.forEach((tab,index)=>{
 const panel=panelFor(tab);
 attr(tab,'role','tab');
 attr(tab,'aria-controls',panel.id);
 attr(panel,'role','tabpanel');
 panel.tabIndex=0;
 attr(panel,'aria-labelledby',tab.id);
 tab.onclick=()=>setTab(tab.id.slice(4));
 tab.onkeydown=event=>{
  const {key}=event;
  if(!['ArrowRight','ArrowLeft','Home','End'].includes(key))return;
  event.preventDefault();
  const i=key==='Home'?0:key==='End'?tabs.length-1:(index+(key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
  const next=tabs[i];
  setTab(next.id.slice(4));
  next.focus();
 };
});
$('download').onclick=()=>!busy&&last&&download('report',reportJson());
$('copy').onclick=async()=>{
 if(busy||!last)return;
 try{
  await navigator.clipboard.writeText(reportJson());
  setText('copy','Copied ✓');setTimeout(()=>setText('copy','Copy JSON'),1500);
 }catch(e){error(e);}
};
$('export').onclick=async()=>{
 if(busy||!last)return;
 setBusy('Exporting bundle…');
 try{
  download('bundle',bundle?.bytes??pretty(await request('/api/bundle',{id:selected.id})));
  status.textContent='Bundle exported.';
 }catch(e){error(e);}finally{setBusy();}
};
$('upload').onclick=event=>{if(busy)event.preventDefault();};
$('upload').onchange=async({currentTarget:input})=>{
 const file = input.files[0];
 if (!file || busy) {input.value = ''; return; }
 setBusy('Reading bundle…');
 clearResults();
 clearLabContext();
 bundle=null;
 showCase(null,file.name);
 try{
  if (file.size > 9 * 1024 * 1024) throw Error(`${file.name} exceeds 9 MiB.`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  bundle = await bindBytes(bytes);

  setBusy();
  await run();
 }catch(err){error(err,' · Import a corrected bundle or choose a case.');}finally{setBusy();input.value='';}
};
function renderComparison(recording){
 const policies=recording.policies;
 const rows=[
  ['Intent A principal',p=>'<strong class="comparison-value '+esc(p.financialStatus)+'">'+near(p.intentAGross)+' <small>NEAR</small></strong>'],
  ['Payment policy',p=>esc(({within:'Within declared limits',breached:'Policy breached'})[p.financialStatus]??p.financialStatus)],
  ['After restart',p=>esc(p.recovery)],
  ['Intent B principal',p=>inNear(p.intentBGross)],
  ['Required outputs passed',p=>esc(p.requiredOutputsPassed)],
  ['Recorded answer',p=>'<code>'+esc(JSON.stringify(p.answer),true)+'</code>'],
  ['Worker exit code',p=>esc(p.crashExitCode)]
 ];
 const body=rows.map(([label,render])=>`<tr><th scope="row">${label}</th>${
  policies.map(p=>`<td>${render(p)}</td>`).join('')}</tr>`).join('');
 const proof=definitionRows([
  ['Run',recording.atUtc],
  ['Assertions',recording.successful?'All matched':'Some failed'],
  ['Local nodes',recording.ownedNodeStopped===true?'Stopped':'Shutdown not confirmed'],
  ['Native send attempts',recording.nativeSendAttempts],
  ['Evidence SHA256',recording.evidenceSha256]
 ]);
 $('native-content').innerHTML=`<p>Workers crashed after settlement.</p>
${reportTable('<caption>Effects after restart</caption>',['Measure',...policies.map(p=>esc(p.name))],body)}
<details><summary>Reproduction</summary><dl>${proof}</dl></details>`;
}

const dialog=$('native-dialog');
$('native-btn').onclick=async()=>{
 if(busy)return;
 dialog.showModal();
 const message='Loading comparison…';
 setBusy(message);
 setText('native-content',message);
 try{
  const comparison=await request('/api/native-result');
  if(dialog.open)renderComparison(comparison);
 }catch(e){if(dialog.open)setText('native-content',e.message);}
 finally{status.textContent='';setBusy();}
};
$('close-native').onclick=()=>dialog.close();

function reportGate(report){
 if(report.invocation.status!=='assessed')return 2;
 const cs=report.constraints,us=report.utility.required;
 if(cs.some(c=>c.status==='breached')||us.some(u=>u.status==='failed'))return 1;
 return report.coverage.financial_scope_complete&&cs.length&&cs.every(c=>c.status==='within')&&us.every(u=>u.status==='passed')?0:2;
}
// End CI gate.
function renderCI(){
 const code=reportGate(last.report);
 setText('ci-expectation',`This input currently exits ${code}: ${['within declared scope, with required work passed','observed policy breach or failed output','inconclusive or rejected; never treat as success'][code]}.`);
}
async function bindBytes(bytes){
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 const key=Array.from(new Uint8Array(digest,0,6),b=>b.toString(16).padStart(2,'0')).join('');
 return {bytes,key:'import-'+key};
}
const sameJSON=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?'['+value.map(sameJSON).join(',')+']':'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+sameJSON(value[key])).join(',')+'}';
function projectLabReport(report){
 return {constraints:Object.fromEntries(report.constraints.map(c=>[c.id,{exact_total:c.exact_total??null,status:c.status}])),
  utility:Object.fromEntries(report.utility.required.map(u=>[u.id,u.status])),financial_scope_complete:report.coverage.financial_scope_complete,gate:reportGate(report)};
}
function checkedLabCase(row){
 if(row?.matches!==true||row.bundle?.format!=='agent-crash-lab/bundle-v1'||row.bundle.classification!=='synthetic'
  ||row.blueprint?.format!=='agent-crash-lab/scenario-v1'||!Number.isInteger(row.blueprint.seed)||!Number.isInteger(row.blueprint.case)
  ||!row.actual||sameJSON(row.actual)!==sameJSON(row.expected)||![0,1,2].includes(row.actual.gate))throw Error('Scenario Lab returned an invalid comparison. No finding certified.');
 return row;
}
function clearLabContext(){labCurrent=labReduction=null;renderLabContext();setText('lab-status','Current recording has no reduction blueprint. Generate a set or select a generated case.');}
function renderLabContext(){
 $('lab-selection').hidden=!labCurrent;
 $('lab-reduce').disabled=!labCurrent?.eligiblePredicate;
 $('lab-trace').hidden=$('lab-original').hidden=$('lab-reduced').hidden=!labReduction;
 for(let i=0;i<labCases.length;i++)attr($('lab-cases-list').children[i],'aria-current',!!labCurrent&&sameJSON(labCurrent.blueprint)===sameJSON(labCases[i].blueprint));
 if(!labCurrent)return;
 setText('lab-predicate',labCurrent.eligiblePredicate?`Finding eligible for reduction: ${labCurrent.eligiblePredicate}. Successful complementary checks must stay successful.`:'This case has no eligible single-axis finding. Keep it as an allowed-work or uncertainty control.');
 if(!labReduction){setText('lab-reduction','');return;}
 const {before,after,predicate,deletionMinimal,budgetExhausted,assessments}=labReduction.reduction;
 setText('lab-reduction',`${before.transactions} transactions / ${before.actions} actions → ${after.transactions} / ${after.actions}. ${predicate} preserved; authority and required-work controls unchanged. ${assessments} trials. ${deletionMinimal===true?'Single-deletion minimality checked; no global minimum claimed.':'Minimality not established.'}${budgetExhausted?' Budget exhausted.':''}`);
}
async function loadLabCase(row,keepReduction=false){
 if(busy)return;
 checkedLabCase(row);if(!keepReduction)labReduction=null;
 setBusy('Preparing generated input…');clearResults();
 try{
  bundle=await bindBytes(new TextEncoder().encode(JSON.stringify(row.bundle)));
  labCurrent=row;
  if(!keepReduction)setText('lab-status',labCases.length+' generated comparisons available. '+oracleLabel(row.oracleMode)+'.');
  showCase(null,`Synthetic seed ${row.blueprint.seed}, case ${row.blueprint.case}${labReduction?.reduced===row?' · reduced':''}. No network execution.`);
  setText('title',labReduction?.reduced===row?'Reduced counterexample':`Generated episode ${row.blueprint.case}`);
  setText('scenario-kind','Generated counterfactual');
  renderLabContext();
 }finally{setBusy();}
 await run();
}
const oracleLabel=mode=>mode==='isolated-python-process'?'Oracle: separate Python process':mode==='separate-module-same-browser-runtime'?'Oracle: separate module in this browser runtime; no process isolation':null;
const labInteger=(id,max)=>{
 const text=$(id).value,value=Number(text);
 if(!/^[0-9]+$/.test(text)||!Number.isSafeInteger(value)||value<0||value>max)throw Error('Use a whole number within the displayed range.');
 return value;
};
$('lab-open').onclick=()=>{if(!busy){$('lab-panel').open=true;$('lab-panel').querySelector('summary').focus();$('lab-panel').scrollIntoView({block:'start',behavior:'instant'});}};
$('lab-form').onsubmit=async event=>{
 event.preventDefault();if(busy)return;
 let next;
 try{
  const seed=labInteger('lab-seed',4294967295),cases=labInteger('lab-cases',12);
  if(!cases)throw Error('Choose at least one case.');
  setBusy('Generating & checking…');clearResults();clearLabContext();bundle=null;
  labCases=[];$('lab-cases-list').replaceChildren();showCase(null,'Generating new synthetic inputs.');
  const data=await request('/api/lab/search',{seed,cases}),mode=oracleLabel(data.oracleMode);
  if(!mode||data.verificationExitCode!==0||!Array.isArray(data.cases)||data.cases.length!==cases)throw Error('Incomplete Scenario Lab result. Retry the search.');
  labCases=data.cases.map(checkedLabCase);
  $('lab-cases-list').replaceChildren(...labCases.map((row,index)=>{
   const button=document.createElement('button');button.type='button';button.textContent=`Case ${row.blueprint.case} · ${['within scope','observed failure','unknown'][row.actual.gate]}`;
   button.onclick=()=>!busy&&loadLabCase(labCases[index]);return button;
  }));
  setText('lab-status',`${cases} comparisons matched. ${data.gates['0']} within scope · ${data.gates['1']} observed failures · ${data.gates['2']} unknown. ${mode}.`);
  next=labCases.find(row=>row.eligiblePredicate)||labCases[0];
 }catch(e){setText('lab-status','Search did not complete. No result certified.');error(e);}
 finally{setBusy();}
 if(next)await loadLabCase(next);
};
$('lab-reduce').onclick=async()=>{
 if(busy||!labCurrent?.eligiblePredicate)return;
 const source=labCurrent;let next;
 try{
  const budget=labInteger('lab-budget',128);if(!budget)throw Error('Choose a budget of at least one assessment.');
  setBusy('Reducing the same finding…');clearResults();
  const data=await request('/api/lab/shrink',{blueprint:source.blueprint,budget});
  checkedLabCase(data.original);checkedLabCase(data.reduced);
  if(!oracleLabel(data.oracleMode)||data.verificationExitCode!==0||sameJSON(data.original.blueprint)!==sameJSON(source.blueprint)
   ||sameJSON(data.reduced.blueprint.intents)!==sameJSON(source.blueprint.intents)||data.reduction?.predicate!==source.eligiblePredicate)throw Error('Reduction changed its authority or finding. No reduction certified.');
  labReduction=data;next=data.reduced;
  setText('lab-status',`Fresh reduction completed. ${oracleLabel(data.oracleMode)}.`);
 }catch(e){clearLabContext();setText('lab-status','Reduction did not complete. No reduction certified.');error(e);}
 finally{setBusy();}
 if(next)await loadLabCase(next,true);
};
$('lab-blueprint').onclick=()=>!busy&&labCurrent&&download('blueprint',pretty(labCurrent.blueprint));
$('lab-trace').onclick=()=>!busy&&labReduction&&download('reduction',pretty(labReduction.reduction));
$('lab-original').onclick=()=>labReduction&&loadLabCase(labReduction.original,true);
$('lab-reduced').onclick=()=>labReduction&&loadLabCase(labReduction.reduced,true);
$('ci-download').onclick=async()=>{
 if(busy||!last)return;setBusy('Saving CI input…');
 try{downloadNamed('episode.json',bundle?.bytes??pretty(await request('/api/bundle',{id:selected.id})));status.textContent='Exact input saved as episode.json.';}
 catch(e){error(e);}finally{setBusy();}
};
$('ci-copy').onclick=async()=>{
 if(busy||!last)return;
 try{await navigator.clipboard.writeText($('ci-command').textContent);status.textContent='CI command copied.';}
 catch{
  const command=$('ci-command'),range=document.createRange(),selection=getSelection();
  command.focus();range.selectNodeContents(command);selection.removeAllRanges();selection.addRange(range);
  status.textContent='Clipboard access is unavailable. Copy the selected command manually.';
 }
};

async function start(){
 if(busy)return;
 setBusy('Loading…');
 try{
  const next=await request('/api/catalog'),cases=next?.scenarios;
  if(!Array.isArray(cases)||!cases.length)throw Error('Cannot load cases.');
  nav.innerHTML=cases.map((s,i)=>`<button class="scenario" data-id="${esc(s.id)}"><span class="scenario-index">${i+1}</span><span><b>${esc(s.short)}</b><small>${esc(s.group)}${s.kind==='synthetic'?' / SYNTHETIC':''}</small></span></button>`).join('');
  setText('case-count',cases.length);
  picker.append(...cases.map((s,i)=>new Option((i+1)+'. '+s.short,s.id)));
  catalog=next;
 }catch(e){error(e);return;}
 finally{setBusy();}
 select(findCase(params.get('case'))??catalog.scenarios[0]);
}
start();
