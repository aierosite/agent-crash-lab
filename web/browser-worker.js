'use strict';
const RUNTIME='https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
const root=new URL('../',self.location.href),decoder=new TextDecoder('utf-8',{fatal:true}),loaded=new Set();
let python,catalog,active=false;
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
async function read(path){
 const expected=catalog.files[path];
 if(!expected||path.split('/').some(p=>p==='..'||p===''))throw Error('Unlisted release path');
 const url=new URL(path,root);url.searchParams.set('sha',expected.sha256);
 let response;
 try{response=await fetch(url);}catch(cause){throw Error('Inspection files could not be downloaded. Check your connection and retry setup, or use the offline ZIP.',{cause});}
 if(!response.ok)throw Error('Inspection files could not be loaded. Check your connection and retry setup, or use the offline ZIP.');
 const bytes=new Uint8Array(await response.arrayBuffer());
 if(bytes.byteLength!==expected.bytes||await digest(bytes)!==expected.sha256)throw Error('Inspection files do not match this release. Reload after the update finishes, or use the offline ZIP.');
 return bytes;
}
async function stage(path){
 if(loaded.has(path))return;
 const bytes=await read(path),dir=path.slice(0,path.lastIndexOf('/')+1);
 if(dir)python.FS.mkdirTree('/app/'+dir);
 python.FS.writeFile('/app/'+path,bytes);loaded.add(path);
}
async function boot(id){
 if(python)return;
 postMessage({id,progress:'Starting browser Python…'});
 try{
  const response=await fetch(new URL('catalog.json',self.location.href),{cache:'reload'});
  if(!response.ok)throw Error('Catalog download failed');
  catalog=await response.json();if(catalog.format!=='agent-crash-lab/browser-v1')throw Error('Unsupported catalog');
 }catch(cause){throw Error('The browser case list could not be loaded. Reload and retry setup, or use the offline ZIP.',{cause});}
 try{
  importScripts(RUNTIME+'pyodide.js');
  python=await loadPyodide({indexURL:RUNTIME});
 }catch(cause){throw Error('Browser Python could not start. Check your connection and retry setup, or use the offline ZIP.',{cause});}
 python.FS.mkdir('/app');
 for(const path of ['agent_crash_lab.py','workbench.py','BASELINES.json'])await stage(path);
 python.runPython("import sys,json\nsys.path.insert(0,'/app')\nimport workbench as app");
}
async function route(path,body,id){
 if(path==='/api/token-policy'){
  await stage('token_review.py');await stage('token_policy.py');python.globals.set('policy_input',body);
  try{
   const result=JSON.parse(python.runPython("import runpy\npolicy_api=runpy.run_path('/app/token_policy.py')\ntry:\n    policy_value=policy_api['assess_bundle'](policy_input.to_bytes())\nexcept ValueError as error:\n    policy_value={'error':str(error)}\njson.dumps(policy_value)"));
   if(result.error)throw Error(result.error);return result;
  }finally{python.globals.delete('policy_input');}
 }
 if(path==='/api/token-source-check'){
  await stage(catalog.sourceCorroboration.module);
  let count=0;for(const path of [...catalog.sourceCorroboration.files,...catalog.sourceCorroboration.cases.map(c=>'verification/token-study/'+c.id+'.json')]){
   await stage(path);if(++count%10===0)postMessage({id,progress:'Loading source-check files · '+count});
  }
  python.globals.set('source_body',JSON.stringify(body));
  try{
   const result=JSON.parse(python.runPython("try:\n    source_value=app.token_source_check(json.loads(source_body))\nexcept ValueError as error:\n    source_value={'error':str(error)}\njson.dumps(source_value)"));if(result.error)throw Error(result.error);return result;
  }finally{python.globals.delete('source_body');}
 }
 if(path==='/api/token-review'){
  await stage('token_review.py');python.globals.set('token_input',body);
  try{
   const result=JSON.parse(python.runPython("import runpy\ntoken_api=runpy.run_path('/app/token_review.py')\ntry:\n    token_value=token_api['review'](token_input.to_bytes())\nexcept ValueError as error:\n    token_value={'error':str(error)}\njson.dumps(token_value)"));
   if(result.error)throw Error(result.error);return result;
  }
  finally{python.globals.delete('token_input');}
 }
 if(path==='/api/catalog')return {scenarios:catalog.scenarios,baselines:catalog.baselines.map(r=>r.name)};
 if(path==='/api/native-result')return JSON.parse(decoder.decode(await read('verification/native-crash-comparison.json')));
 if(['/api/lab/search','/api/lab/shrink'].includes(path)){
  const template=catalog.baselines.find(r=>r.name==='split-settlement');
  for(const file of ['tools/scenario_lab.py','episode_oracle.py',template.task,...Object.values(template.sources)])await stage(file);
  python.globals.set('lab_operation_name',path.slice('/api/lab/'.length));
  python.globals.set('lab_body_json',JSON.stringify(body));
  try{return JSON.parse(python.runPython("json.dumps(app.lab_operation(lab_operation_name,json.loads(lab_body_json),isolated=False))"));}
  finally{python.globals.delete('lab_operation_name');python.globals.delete('lab_body_json');}
 }
 if(!['/api/run','/api/bundle','/api/assess'].includes(path))throw Error('Unknown browser operation');
 if(path!=='/api/assess'){
  const scenario=catalog.scenarios.find(s=>s.id===body?.id);if(!scenario)throw Error('Unknown scenario');
  const row=catalog.baselines.find(r=>r.name===scenario.baseline);
  for(const file of [row.task,...Object.values(row.sources)])await stage(file);
 }
 // User inputs are JSON data, never interpolated into executable Python.
 python.globals.set('path',path);
 python.globals.set('body',body);
 try{
  return JSON.parse(python.runPython(`if path=='/api/assess':
    try:
        value=app.assess_bundle(app.decode(body.to_bytes()))
    except (ValueError, RecursionError) as e:
        value={'error':str(e)[:200] or 'Invalid bundle'}
else:
    scenario=app.CATALOG[body.id]
    task,sources=app.data_for(scenario)
    value=app.evaluate(task,sources,scenario) if path=='/api/run' else app.bundle(task,sources,scenario)
if 'execution' in value:
    value['execution'].update(mode='actual-browser-python-assessment',pythonVersion=sys.version.split()[0])
json.dumps(value)`));
 }finally{python.globals.delete('body');}
}
onmessage=async({data:{id,path,body}})=>{
 if(active){postMessage({id,error:'A browser inspection is already running'});return;}
 active=true;
 try{
  if(path==='/api/assess'&&body.byteLength>9*1024*1024)throw Error('Bundle exceeds 9 MiB');
  if(path==='/api/token-review'&&(!body?.byteLength||body.byteLength>2*1024*1024))throw Error('Choose a nonempty token recording no larger than 2 MiB.');
  if(path==='/api/token-policy'&&(!body?.byteLength||body.byteLength>2*1024*1024))throw Error('Choose a nonempty payment-policy bundle no larger than 2 MiB.');
  await boot(id);const result=await route(path,body,id);postMessage({id,result});
 }catch(e){postMessage({id,error:String(e.message||e).trim().split('\n').pop().slice(0,300)});}
 finally{active=false;}
};
