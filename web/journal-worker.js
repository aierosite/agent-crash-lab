'use strict';
const journalRuntime='https://cdn.jsdelivr.net/pyodide/v0.29.5/full/',journalRoot=new URL('../',self.location.href);
let journalPython,journalSources,journalBusy=false;
const journalHash=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
async function journalBoot(id){
 if(journalPython)return;postMessage({id,progress:'Starting browser Python and checking both review sources…'});
 const response=await fetch(new URL('catalog.json',self.location.href),{cache:'reload'});if(!response.ok)throw Error('The source inventory could not load. Reload and retry.');
 const catalog=await response.json(),entry=catalog.nativeJournal;
 if(catalog.format!=='agent-crash-lab/browser-v1'||entry?.module!=='receipt_journal.py'||entry.mathModule!=='receipt_journal_math.py'||entry.runtime!==journalRuntime)throw Error('The journal reviewer is missing from this release. Reload after the update.');
 const sources=await Promise.all([entry.module,entry.mathModule].map(async name=>{
  const expected=catalog.files?.[name];if(!expected)throw Error('A review source is missing from the inventory.');
  const r=await fetch(new URL(name+'?sha='+expected.sha256,journalRoot));if(!r.ok)throw Error('The journal review source could not load.');
  const bytes=new Uint8Array(await r.arrayBuffer()),sha=await journalHash(bytes);if(bytes.length!==expected.bytes||sha!==expected.sha256)throw Error('The review sources do not match this release. Reload after the update.');return {name,bytes,sha};
 }));
 try{importScripts(journalRuntime+'pyodide.js');journalPython=await loadPyodide({indexURL:journalRuntime});}catch{throw Error('Browser Python could not start. Check the connection or use the offline Python reviewer.');}
 journalPython.FS.mkdir('/journal-review');for(const source of sources)journalPython.FS.writeFile('/journal-review/'+source.name,source.bytes);
 journalPython.runPython("import json,runpy\nnative_journal_api=runpy.run_path('/journal-review/receipt_journal.py')");journalSources=sources.map(s=>s.sha);
}
onmessage=async({data})=>{
 const id=data?.id;if(journalBusy){postMessage({id,error:'Another review is still running. Cancel it before starting another.'});return;}
 journalBusy=true;
 try{
  if(!Number.isSafeInteger(id)||!(data.journal instanceof Uint8Array)||!data.journal.length||data.journal.length>4194304||!(data.policy instanceof Uint8Array)||!data.policy.length||data.policy.length>16384)throw Error('Choose a journal up to 4 MiB and payment intent up to 16 KiB.');
  await journalBoot(id);journalPython.globals.set('native_journal_bytes',data.journal);journalPython.globals.set('native_policy_bytes',data.policy);
  let value;try{value=JSON.parse(journalPython.runPython("try:\n    native_journal_result={'report':native_journal_api['assess_bundle'](native_journal_bytes.to_bytes().decode('utf-8'),native_policy_bytes.to_bytes().decode('utf-8'))}\nexcept (ValueError,KeyError,TypeError) as error:\n    native_journal_result={'error':'The supplied journal could not be reviewed: '+str(error)}\njson.dumps(native_journal_result,ensure_ascii=False)"));}finally{journalPython.globals.delete('native_journal_bytes');journalPython.globals.delete('native_policy_bytes');}
  if(value.error)throw Error(value.error);if(value.report?.assessor_sha256!==journalSources[0]||value.report.math_sha256!==journalSources[1])throw Error('The running reviewer differs from the checked sources. Reload and retry.');
  postMessage({id,report:value.report});
 }catch(error){journalPython=null;journalSources=null;postMessage({id,error:String(error.message||'The browser review stopped. Retry or use the offline Python reviewer.').slice(0,400)});}
 finally{journalBusy=false;}
};
