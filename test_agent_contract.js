'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {validateAgentReport,agentCanonical,agentSha}=require('./web/agent-contract.js');
const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'verification/exposure-study/catalog.json'),'utf8'));
const mode='same-interpreter-reference-namespace',clone=x=>JSON.parse(JSON.stringify(x));
function report(id,label='browser'){return JSON.parse(fs.readFileSync(path.join(__dirname,'verification/exposure-study/reports',id+'-'+label+'.json'),'utf8'));}
async function rejection(id,change,repin=false){const value=report(id),meta=clone(catalog.cases.find(c=>c.id===id));change(value);if(repin)meta.reportSha256[mode]=await agentSha(agentCanonical(value));await assert.rejects(validateAgentReport(value,meta,mode,catalog));}
async function main(){
 let accepted=0,rejected=0;
 for(const c of catalog.cases)for(const [label,runtime] of [['local','separate-reference-process'],['browser',mode]]){await validateAgentReport(report(c.id,label),c,runtime,catalog);accepted++;}
 await rejection('fee-protected',r=>{r.case.review_gate=0;r.rows.find(x=>x.id===r.case.id).review_gate=0;},true);rejected++;
 await rejection('role-unguarded',r=>{r.case.review_gate=0;r.rows.find(x=>x.id===r.case.id).review_gate=0;},true);rejected++;
 await rejection('fee-protected',r=>{r.case.bill_status='met';r.rows.find(x=>x.id===r.case.id).bill_status='met';},true);rejected++;
 await rejection('role-unguarded',r=>{r.timeline[1].model_request_utf8+='\nInvented model context';},true);rejected++;
 await rejection('role-unguarded',r=>{const row=r.timeline.find(x=>x.sdk_effects.length);row.sdk_effects[0].amount=String(BigInt(row.sdk_effects[0].amount)+1n);},true);rejected++;
 await rejection('role-protected',r=>{r.payment_input.task_utf8+=' ';},true);rejected++;
 await rejection('fee-protected',r=>{r.communication.finish_observed=true;},true);rejected++;
 await rejection('role-protected',r=>{r.verification.new_model_calls=1;},true);rejected++;
 await rejection('role-unguarded',r=>{r.case.id='role-protected';},true);rejected++;
 await rejection('role-unguarded',r=>{r.comparison.first_different_tool_outcome.selected_http_status=409;},true);rejected++;
 console.log(JSON.stringify({acceptedCompleteResponses:accepted,rejectedIncoherentResponses:rejected,repinnedOuterDigestDoesNotBypassConsumedFieldChecks:true,scope:'UI response identity and coherence, not independent financial accuracy'}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
