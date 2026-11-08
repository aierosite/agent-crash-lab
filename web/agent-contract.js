'use strict';
const agentCanonical=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?'['+value.map(agentCanonical).join(',')+']':'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+agentCanonical(value[k])).join(',')+'}';
const agentSha=async text=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,'0')).join('');
function agentNeed(ok){if(!ok)throw Error('The recorded-run response does not match its verified inputs. Retry, or use the offline verifier.');}
function agentBounded(value,depth=0,count={n:0}){
 agentNeed(depth<=36&&++count.n<=40000);
 if(value===null||typeof value==='boolean')return;
 if(typeof value==='string'){agentNeed(value.length<=262144);return;}
 if(typeof value==='number'){agentNeed(Number.isSafeInteger(value));return;}
 agentNeed(typeof value==='object');const array=Array.isArray(value);agentNeed(Object.getPrototypeOf(value)===(array?Array.prototype:Object.prototype));const descriptors=Object.getOwnPropertyDescriptors(value);
 agentNeed(Object.keys(value).length<=(array?128:128));for(const key of Object.keys(value)){agentNeed(Object.hasOwn(descriptors[key],'value'));agentBounded(descriptors[key].value,depth+1,count);}
}
async function validateAgentReport(report,selected,mode,catalog){
 agentBounded(report);agentNeed(report.format==='agent-crash-lab/recorded-agent-review-v1'&&report.case?.id===selected.id&&report.verification?.mode===mode);
 const r=report.case,v=report.verification;agentNeed(report.rows?.length===6&&catalog.cases.length===6&&report.timeline?.length===r.model_decisions+1);
 agentNeed(['met','unmet','unknown'].includes(r.bill_status)&&[0,1,2].includes(r.payment_gate)&&typeof r.bill_criterion_observed==='boolean'&&typeof r.closed_bounded_trajectory==='boolean');
 agentNeed(r.bill_status===(r.bill_criterion_observed?'met':r.closed_bounded_trajectory?'unmet':'unknown'));
 const gate=r.bill_status==='unmet'||r.payment_gate===1?1:r.bill_status==='unknown'||r.payment_gate===2?2:0;agentNeed(r.review_gate===gate);
 const seen=new Set();for(const row of report.rows){agentNeed(catalog.cases.some(c=>c.id===row.id)&&!seen.has(row.id));seen.add(row.id);}
 agentNeed(agentCanonical(report.rows.find(x=>x.id===r.id))===agentCanonical(r));agentNeed(report.rows.some(x=>x.id===report.paired_case&&x.profile===r.profile&&x.policy!==r.policy));
 agentNeed(report.bill_reference?.status===r.bill_status&&report.bill_reference.observed_value===r.bill_criterion_observed&&report.payment_report?.gate===r.payment_gate&&report.communication?.finish_observed===r.finish_observed);
 agentNeed(v.original_full_objects_matched===true&&v.current_payment_report_matched===true&&v.all_raw_model_http_sdk_links_replayed===true&&v.raw_timestamps_preserved===true&&v.independent_blind_evaluation===false);
 agentNeed(v.study_index_sha256===catalog.studyIndexSha256&&v.current_assessor_sha256===catalog.assessorSha256&&['new_model_calls','new_sdk_calls','new_transactions','new_chain_rpc'].every(k=>v[k]===0));
 agentNeed(report.exposure.delivered_to_model===r.exposed_context_delivered&&report.exposure.attack_case===(r.profile!=='clean'));
 const decimal=x=>typeof x==='string'&&/^(0|[1-9][0-9]{0,38})$/.test(x);agentNeed(decimal(r.gross_atomic));let gross=0n,payments=0,finishes=0;const calls=new Set();
 for(const [index,event] of report.timeline.entries()){
  agentNeed(typeof event.request_utf8==='string'&&typeof event.response_utf8==='string'&&Number.isInteger(event.http_status)&&event.http_status>=100&&event.http_status<=599&&Array.isArray(event.sdk_effects));
  if(index===0)agentNeed(event.kind==='caller-prefetch'&&event.model_call_id===null&&event.sdk_effects.length===0&&event.http_status===200);
  else{agentNeed(event.kind==='model-decision'&&Number.isSafeInteger(event.model_call_id)&&!calls.has(event.model_call_id));calls.add(event.model_call_id);agentNeed(typeof event.model_request_utf8==='string'&&typeof event.model_response_utf8==='string');agentNeed(await agentSha(event.model_request_utf8)===event.model_request_sha256&&await agentSha(event.model_response_utf8)===event.model_response_sha256);}
  for(const effect of event.sdk_effects){agentNeed(decimal(effect.amount)&&BigInt(effect.amount)>0n&&effect.method==='ft_transfer');gross+=BigInt(effect.amount);payments++;}
  if(event.tool==='finish'&&event.http_status===200)finishes++;
 }
 agentNeed(gross===BigInt(r.gross_atomic)&&payments===r.sdk_mock_payments&&finishes===(r.finish_observed?1:0));
 const pair=report.comparison;agentNeed(pair?.post_hoc_descriptive_comparison===true&&Number.isSafeInteger(pair.shared_initial_model_requests_and_tools)&&pair.shared_initial_model_requests_and_tools>=0&&pair.shared_initial_model_requests_and_tools<=r.model_decisions);
 if(pair.first_different_tool_outcome){const d=pair.first_different_tool_outcome;agentNeed(Number.isInteger(d.decision)&&d.decision>0&&d.decision<=pair.shared_initial_model_requests_and_tools);const event=report.timeline[d.decision];agentNeed(event.tool===d.tool&&event.http_status===d.selected_http_status&&event.model_request_sha256===d.same_model_request_sha256&&event.sdk_effects.length===d.selected_sdk_effects);}
 agentNeed(report.payment_input?.format==='agent-crash-lab/token-policy-bundle-v1'&&typeof report.payment_input.task_utf8==='string'&&typeof report.payment_input.evidence_utf8==='string');
 agentNeed(await agentSha(report.payment_input.task_utf8)===report.payment_report.task_sha256&&await agentSha(report.payment_input.evidence_utf8)===report.payment_report.evidence_sha256);
 const serialized=agentCanonical(report);agentNeed(new TextEncoder().encode(serialized).length<=2*1024*1024);agentNeed(await agentSha(serialized)===selected.reportSha256[mode]);return report;
}
if(typeof module!=='undefined')module.exports={validateAgentReport,agentCanonical,agentSha};
