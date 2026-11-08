'use strict';
// Executes the actual client with controlled async schedules and test doubles.
// This is not a browser run or a test of Pyodide execution.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const rows=JSON.parse(fs.readFileSync('verification/receipt-journal/samples.json','utf8'));
const selected=rows[0],paths=[selected.journal,selected.policy],bytes=paths.map(p=>fs.readFileSync(p)),files=Object.fromEntries(paths.map((p,i)=>[p,{bytes:bytes[i].length,sha256:crypto.createHash('sha256').update(bytes[i]).digest('hex')}]))
files['receipt_journal.py']={sha256:'a'.repeat(64)};files['receipt_journal_math.py']={sha256:'b'.repeat(64)};
const config={format:'agent-crash-lab/native-journal-workbench-v1',module:'receipt_journal.py',mathModule:'receipt_journal_math.py',samples:[selected],files};
const response=b=>({ok:true,arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)});
async function scenario(mode){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,value:'',files:[],textContent:'',dataset:{},replaceChildren(){},append(){}});return elements.get(id);};
 let release;const delayed=new Promise(resolve=>release=resolve),workers=[],timers=new Set(),posts=[];
 const context=vm.createContext({document:{getElementById:el,createElement:()=>({append(){}}),documentElement:{dataset:{}},querySelectorAll:()=>[]},localStorage:{getItem:()=>null,setItem(){}},location:new URL('https://local.test/web/journal.html?browser=1'),URLSearchParams,console,Uint8Array,TextEncoder,TextDecoder,crypto:crypto.webcrypto,URL,Blob,AbortController,
  addEventListener(){},setTimeout(fn){timers.add(fn);return fn;},clearTimeout(fn){timers.delete(fn);},
  fetch:path=>path==='catalog.json'?Promise.resolve({ok:true,json:async()=>({nativeJournal:config,files})}):mode==='late-fetch'?delayed:Promise.resolve(response(bytes[path.includes('policies')?1:0])),
  nativeJournalBinding:async()=>({journal:new Uint8Array(bytes[0]),policy:new Uint8Array(bytes[1])}),journalCanonical:JSON.stringify,
  Worker:class{constructor(){workers.push(this);}postMessage(data){posts.push(data);}terminate(){this.terminated=true;}},validateNativeJournalReport(){throw Error('Late worker output must never be validated');}});
 vm.runInContext(fs.readFileSync('web/journal.js','utf8'),context,{filename:'web/journal.js'});await new Promise(setImmediate);
 el('sample').value=selected.id;
 if(mode==='late-files'){
  el('journal-input').files=[{size:bytes[0].length,arrayBuffer:async()=>{await delayed;return bytes[0];}}];el('policy-input').files=[{size:bytes[1].length,arrayBuffer:async()=>bytes[1]}];
  const action=el('review-input').onclick();el('cancel').onclick();release();await action;
 }else if(mode==='late-fetch'){
  const action=el('run').onclick();el('cancel').onclick();release(response(bytes[0]));await action;
 }else{
  await el('run').onclick();assert.equal(workers.length,1);assert.equal(posts.length,1);const worker=workers[0],id=posts[0].id;
  el('cancel').onclick();assert.equal(worker.terminated,true);await worker.onmessage({data:{id,report:{forged:true}}});
 }
 assert.equal(el('results').hidden,true);assert.equal(el('save-review').disabled,true);assert.equal(el('save-journal').disabled,true);assert.equal(el('save-policy').disabled,true);assert.equal(el('error').hidden,true);assert.equal(timers.size,0);
 assert.equal(el('status').textContent,'Review cancelled. No result was accepted.');
 if(mode!=='late-worker')assert.equal(workers.length,0);
 return {schedule:mode,workersStarted:workers.length,activeTimers:timers.size,resultAccepted:false,actualBrowserRun:false};
}
(async()=>{const results=[];for(const mode of ['late-fetch','late-files','late-worker'])results.push(await scenario(mode));console.log(JSON.stringify({results}));})().catch(error=>{console.error(error);process.exitCode=1;});
