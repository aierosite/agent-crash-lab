'use strict';
const agentRoot=new URL('../',self.location.href),agentRuntime='https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
let agentPython,agentCatalog,agentActive=false;const agentLoaded=new Set();
async function agentLoad(path){
 const expected=agentCatalog.files[path];if(!expected||path.split('/').some(p=>p==='..'||p===''))throw Error('Unlisted recorded-study file');
 const url=new URL(path,agentRoot);url.searchParams.set('sha',expected.sha256);let response;try{response=await fetch(url);}catch{throw Error('Recorded-study files could not be downloaded. Check the connection and retry, or use the offline ZIP.');}
 if(!response.ok)throw Error('Recorded-study files could not load. Check the connection and retry, or use the offline ZIP.');const bytes=new Uint8Array(await response.arrayBuffer());
 const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
 if(bytes.length!==expected.bytes||digest!==expected.sha256)throw Error('The recorded study does not match this release. Reload after the update finishes.');
 const slash=path.lastIndexOf('/');if(slash>=0)agentPython.FS.mkdirTree('/app/'+path.slice(0,slash));agentPython.FS.writeFile('/app/'+path,bytes);agentLoaded.add(path);
}
async function agentBoot(id){
 if(agentPython)return;
 const response=await fetch(new URL('catalog.json',self.location.href),{cache:'reload'});if(!response.ok)throw Error('The recorded-run list could not load. Reload and retry.');agentCatalog=await response.json();
 if(agentCatalog.format!=='agent-crash-lab/browser-v1'||!Array.isArray(agentCatalog.agentRuns?.files))throw Error('This release has no recorded-agent study. Reload after the update.');
 postMessage({id,progress:'Starting browser Python for recorded-data replay…'});try{importScripts(agentRuntime+'pyodide.js');agentPython=await loadPyodide({indexURL:agentRuntime});}catch{throw Error('Browser Python could not start. Check the connection and retry, or use the offline ZIP.');}agentPython.FS.mkdir('/app');
 let done=0;const paths=agentCatalog.agentRuns.files.filter(p=>!agentLoaded.has(p));
 for(let offset=0;offset<paths.length;offset+=6){await Promise.all(paths.slice(offset,offset+6).map(agentLoad));done+=Math.min(6,paths.length-offset);postMessage({id,progress:'Verifying recorded sources and responses · '+done+' / '+paths.length});}
 agentPython.runPython("import sys,json,runpy\nsys.path.insert(0,'/app')\nagent_api=runpy.run_path('/app/agent_review.py')");
}
onmessage=async({data})=>{
 const {id,body}=data||{};if(agentActive){postMessage({id,error:'A recorded-run check is already in progress.'});return;}agentActive=true;
 try{
  if(!Number.isSafeInteger(id)||!body||Object.keys(body).join()!=='id'||typeof body.id!=='string'||body.id.length>64)throw Error('Choose a valid recorded case.');
  await agentBoot(id);postMessage({id,progress:'Replaying raw links, the original bill reference and current payment checks…'});agentPython.globals.set('agent_case_id',body.id);
  try{const result=JSON.parse(agentPython.runPython("json.dumps(agent_api['review'](agent_case_id,portable=True))"));postMessage({id,result});}
  finally{agentPython.globals.delete('agent_case_id');}
 }catch(error){postMessage({id,error:String(error.message||error).split('\n').pop().slice(0,300)});agentPython=null;agentCatalog=null;agentLoaded.clear();}
 finally{agentActive=false;}
};
