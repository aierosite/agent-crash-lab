'use strict';
const stateRuntime='https://cdn.jsdelivr.net/pyodide/v0.29.5/full/',stateRoot=new URL('../',self.location.href);let statePython,stateSourceSha,stateBusy=false;
const stateHashBytes=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
async function stateBoot(id){
 if(statePython)return;postMessage({id,progress:'Starting browser Python…'});
 const response=await fetch(new URL('catalog.json',self.location.href),{cache:'reload'});if(!response.ok)throw Error('The source inventory could not load. Reload and retry.');const catalog=await response.json(),meta=catalog.metadataReview,expected=catalog.files?.['state_review.py'];
 if(catalog.format!=='agent-crash-lab/browser-v1'||meta?.module!=='state_review.py'||meta.runtime!==stateRuntime||!expected)throw Error('The metadata reviewer is missing from this release. Reload after the update.');
 const file=await fetch(new URL('state_review.py?sha='+expected.sha256,stateRoot));if(!file.ok)throw Error('The review source could not load.');const raw=new Uint8Array(await file.arrayBuffer());stateSourceSha=await stateHashBytes(raw);if(raw.length!==expected.bytes||stateSourceSha!==expected.sha256)throw Error('The review source does not match this release. Reload after the update.');
 try{importScripts(stateRuntime+'pyodide.js');statePython=await loadPyodide({indexURL:stateRuntime});}catch{throw Error('Browser Python could not start. Check the connection and retry, or use the offline CLI.');}
 statePython.FS.mkdir('/review');statePython.FS.writeFile('/review/state_review.py',raw);statePython.runPython("import json,runpy\nmetadata_api=runpy.run_path('/review/state_review.py')");
}
onmessage=async({data})=>{
 const {id,bundle}=data||{};if(stateBusy){postMessage({id,error:'A review is already running. Wait or cancel it.'});return;}stateBusy=true;
 try{
  if(!Number.isSafeInteger(id)||!(bundle instanceof Uint8Array)||bundle.byteLength>1048576)throw Error('Choose a metadata bundle no larger than 1 MiB.');
  await stateBoot(id);postMessage({id,progress:'Checking each supplied state transition…'});statePython.globals.set('metadata_bundle',bundle);
  let value;try{value=JSON.parse(statePython.runPython("try:\n    metadata_value={'report':metadata_api['assess_bundle'](metadata_bundle.to_bytes())}\nexcept metadata_api['InputError'] as error:\n    metadata_value={'error':str(error)}\njson.dumps(metadata_value)"));}finally{statePython.globals.delete('metadata_bundle');}
  if(value.error){postMessage({id,error:value.error});return;}
  if(value.report.assessor_sha256!==stateSourceSha)throw Error('The review source does not match the expected code.');postMessage({id,report:value.report});
 }catch(error){statePython=null;postMessage({id,error:String(error.message||error).split('\n').pop().slice(0,400)});}
 finally{stateBusy=false;}
};
