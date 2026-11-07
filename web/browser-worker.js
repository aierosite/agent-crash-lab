'use strict';
const RUNTIME='https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
const root=new URL('../',self.location.href),decoder=new TextDecoder('utf-8',{fatal:true}),loaded=new Set();
let python,catalog,active=false;
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
async function read(path){
 const expected=catalog.files[path];
 if(!expected||path.split('/').some(p=>p==='..'||p===''))throw Error('Unlisted release path');
 const url=new URL(path,root);url.searchParams.set('sha',expected.sha256);
 const response=await fetch(url);if(!response.ok)throw Error(`Release file unavailable: ${path}`);
 const bytes=new Uint8Array(await response.arrayBuffer());
 if(bytes.byteLength!==expected.bytes||await digest(bytes)!==expected.sha256)throw Error(`Release file changed: ${path}. Reload after deployment finishes.`);
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
 const response=await fetch(new URL('catalog.json',self.location.href),{cache:'reload'});if(!response.ok)throw Error('Browser catalog unavailable');
 catalog=await response.json();if(catalog.format!=='agent-crash-lab/browser-v1')throw Error('Unsupported browser catalog');
 importScripts(RUNTIME+'pyodide.js');
 python=await loadPyodide({indexURL:RUNTIME});python.FS.mkdir('/app');
 for(const path of ['agent_crash_lab.py','workbench.py','BASELINES.json'])await stage(path);
 python.runPython("import sys,json\nsys.path.insert(0,'/app')\nimport workbench as app");
}
async function route(path,body){
 if(path==='/api/catalog')return {scenarios:catalog.scenarios,baselines:catalog.baselines.map(r=>r.name)};
 if(path==='/api/native-result')return JSON.parse(decoder.decode(await read('verification/native-crash-comparison.json')));
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
  await boot(id);const result=await route(path,body);postMessage({id,result});
 }catch(e){postMessage({id,error:String(e.message||e).trim().split('\n').pop().slice(0,300)});}
 finally{active=false;}
};
