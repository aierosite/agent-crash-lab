'use strict';
// Execute the actual client under a controlled async response schedule. The DOM
// and Worker are minimal test doubles; this is not counted as a browser run.
const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');
const assert=require('node:assert/strict'),source=process.argv[2]||'web/state.js',baseline=source.includes('before-cancel');
async function main(){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,value:'',files:[],textContent:'',dataset:{},replaceChildren(){},append(){}});return elements.get(id);};
 const sample=fs.readFileSync('verification/metadata-review/inputs/permitted-address.json'),sha=crypto.createHash('sha256').update(sample).digest('hex');
 const config={format:baseline?'agent-crash-lab/private-state-portability-v1':'agent-crash-lab/metadata-workbench-v1',files:{'state_review.py':{sha256:'a'.repeat(64)},'sample.json':{bytes:sample.length,sha256:sha}},samples:Array.from({length:35},(_,i)=>({id:i?'unused-'+i:'one',title:'one',path:'sample.json',group:'Constructed controls'}))};
 let release;const delayed=new Promise(resolve=>release=resolve),workers=[],timers=new Set();
 const context=vm.createContext({document:{getElementById:el,createElement:()=>({append(){}}),documentElement:{dataset:{}},querySelectorAll:()=>[]},localStorage:{getItem:()=>null,setItem(){}},location:new URL('https://local.test/web/state.html?browser=1'),URLSearchParams,console,Uint8Array,TextEncoder,TextDecoder,crypto:crypto.webcrypto,URL,Blob,
  addEventListener(){},setTimeout(fn){timers.add(fn);return fn;},clearTimeout(fn){timers.delete(fn);},
  fetch:path=>['config.json','catalog.json'].includes(path)?Promise.resolve({ok:true,json:async()=>baseline?config:{metadataReview:config,files:config.files}}):delayed,
  metadataBundleBinding:async()=>({assessor_sha256:'a'.repeat(64),policy_sha256:'b'.repeat(64),capture_sha256:'c'.repeat(64)}),
  Worker:class{constructor(){workers.push(this);}postMessage(){}terminate(){this.terminated=true;}},validateMetadataReport(){}});
 vm.runInContext(fs.readFileSync(source,'utf8'),context,{filename:source});await new Promise(setImmediate);
 el('sample').value='one';const action=el('run').onclick();assert.equal(el('cancel').hidden,false);
 el('cancel').onclick();assert.equal(el('results').hidden,true);
 release({ok:true,arrayBuffer:async()=>sample.buffer.slice(sample.byteOffset,sample.byteOffset+sample.byteLength)});await action;
 const observed={source,controlledSchedule:'Cancel after sample fetch begins; release the successful fetch only after cancellation',workersStartedAfterCancellation:workers.length,timersAfterCancellation:timers.size,status:el('status').textContent,expectedNoRestart:!baseline,actualBrowserRun:false};
 if(baseline)assert.equal(workers.length,1,'Reproduce the late-response defect');else{assert.equal(workers.length,0);assert.equal(timers.size,0);assert.equal(el('status').textContent,'Review cancelled. No result was accepted.');}
 console.log(JSON.stringify(observed));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
