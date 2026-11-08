'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {metadataBundleBinding,validateMetadataReport}=require('./web/state-contract.js');
async function main(){
 const data=JSON.parse(fs.readFileSync('verification/metadata-review/vectors.json','utf8')),sha=data.summary.sourceSha256;
 const pairs=data.cases.filter(c=>c.mode==='pair'&&c.native.report),encoder=new TextEncoder();let accepted=0,rejected=0;
 for(const row of pairs){
  const authority=Buffer.from(row.authority_b64,'base64').toString('utf8'),capture=Buffer.from(row.capture_b64,'base64').toString('utf8');
  const raw=encoder.encode(JSON.stringify({format:'agent-crash-lab/banking-metadata-bundle-v1',authority_utf8:authority,capture_utf8:capture}));
  const binding=await metadataBundleBinding(raw,sha);validateMetadataReport(row.native.report,binding);accepted++;
 }
 for(const row of data.cases.filter(c=>c.mode==='bundle'&&c.native.report)){const binding=await metadataBundleBinding(Buffer.from(row.bundle_b64,'base64'),sha);validateMetadataReport(row.native.report,binding);accepted++;}
 const good=data.cases.find(c=>c.id==='bundle-high-precision'),raw=Buffer.from(good.bundle_b64,'base64'),text=raw.toString('utf8'),obj=JSON.parse(text),bad=[
  text.replace('"format":','"format":"wrong","format":'),
  text.replace('"capture_utf8":','"capture_utf8":"wrong","capture_utf8":'),
  JSON.stringify({...obj,extra:'no'}),
  JSON.stringify({...obj,authority_utf8:JSON.parse(obj.authority_utf8)}),
  text+' trailing',text.replace(/}$/,',}'),text.replace(/}$/,',"__proto__":"no"}'),
  JSON.stringify({...obj,authority_utf8:'\ud800'}),'\ufeff'+text,
 ];
 for(const value of bad){await assert.rejects(()=>metadataBundleBinding(encoder.encode(value),sha));rejected++;}
 for(const bytes of [Buffer.from(text,'utf16le'),new Uint8Array(1048577)]){await assert.rejects(()=>metadataBundleBinding(bytes,sha));rejected++;}
 const bound=await metadataBundleBinding(raw,sha);assert.equal(bound.policy_sha256,crypto.createHash('sha256').update(obj.authority_utf8).digest('hex'));
 assert.notEqual(bound.policy_sha256,crypto.createHash('sha256').update(JSON.stringify(JSON.parse(obj.authority_utf8))).digest('hex'));
 const result={exactInputBindingsAccepted:accepted,rejectedMalformedEnvelopes:rejected,highPrecisionNeverParsedOrRepacked:true,meaning:'Flat string-only envelope transport validation and SHA binding, not state semantic grading'};
 console.log(JSON.stringify(result));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
