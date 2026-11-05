'use strict';
// Optional WebAssembly host. All assessment rules remain in the exact Python core.
const RUNTIME='https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
const root=new URL('../',self.location.href),decoder=new TextDecoder('utf-8',{fatal:true}),loaded=new Set();
let python,catalog,active=false;
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
async function read(path){
 const expected=catalog.files[path];
 if(!expected||path.startsWith('/')||path.split('/').some(p=>p==='..'||p===''))throw Error('Unlisted release path');
 const response=await fetch(new URL(path,root));if(!response.ok)throw Error(`Release file unavailable: ${path}`);
 const bytes=new Uint8Array(await response.arrayBuffer());
 if(bytes.byteLength!==expected.bytes||await digest(bytes)!==expected.sha256)throw Error(`Release file changed: ${path}. Reload after deployment finishes.`);
 return bytes;
}
async function stage(path){
 if(loaded.has(path))return;
 const bytes=await read(path),parts=path.split('/');parts.pop();if(parts.length)python.FS.mkdirTree('/app/'+parts.join('/'));
 python.FS.writeFile('/app/'+path,bytes);loaded.add(path);
}
async function boot(id){
 if(python)return;
 postMessage({id,progress:'Downloading Python 3.13 for this browser. First load may take a minute…'});
 const response=await fetch(new URL('catalog.json',self.location.href));if(!response.ok)throw Error('Browser catalog unavailable');
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
 python.globals.set('request_json',JSON.stringify({path,body}));
 const result=python.runPython(`req=json.loads(request_json)
if req['path']=='/api/assess':
    value=app.assess_bundle(req['body'])
else:
    scenario=app.CATALOG[req['body']['id']]
    task,sources=app.data_for(scenario)
    value=app.evaluate(task,sources,scenario) if req['path']=='/api/run' else {'format':'agent-crash-lab/bundle-v1','task_utf8':task.decode(),'sources_utf8':{k:v.decode() for k,v in sources.items()},'classification':scenario['kind']}
if 'execution' in value:
    value['execution']['mode']='actual-browser-python-assessment'
    value['execution']['pythonVersion']=sys.version.split()[0]
json.dumps(value)`);
 return JSON.parse(result);
}
onmessage=async({data:{id,path,body}})=>{
 if(active){postMessage({id,error:'A browser inspection is already running'});return;}
 active=true;
 try{
  if(body!==undefined&&new TextEncoder().encode(JSON.stringify(body)).byteLength>9*1024*1024)throw Error('Bundle exceeds 9 MiB');
  await boot(id);const result=await route(path,body);postMessage({id,result});
 }catch(e){postMessage({id,error:String(e.message||e).trim().split('\n').pop().slice(0,300)});}
 finally{active=false;}
};
