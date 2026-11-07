'use strict';
// Source-informed contract regressions. Requires Node only for development/CI.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {spawnSync}=require('node:child_process');
const source=fs.readFileSync(__dirname+'/web/app.js','utf8');
const start=source.indexOf('function validateInspection(data){');
const end=source.indexOf('// End report contract.',start);
assert(start>=0&&end>start,'The tested contract must be the browser contract');
const validate=vm.runInNewContext('('+source.slice(start,end)+')');
const corpusProgram=`
from pathlib import Path
import json, runpy
w=runpy.run_path('workbench.py'); root=Path('.')
rows=[]
for name,row in w['BASELINES'].items():
    rows.append({'name':name,'response':w['evaluate']((root/row['task']).read_bytes(),
        {key:(root/path).read_bytes() for key,path in row['sources'].items()})})
for scenario in w['CURATED']:
    rows.append({'name':scenario['id'],'response':w['evaluate'](*w['data_for'](scenario))})
# The engine may return unknown rows for invalid owner declarations.
task,sources=w['data_for'](w['CATALOG']['legitimate-installments'])
for name,change in [('invalid-constraint',lambda t:t['constraints'].append(None)),
                    ('invalid-required',lambda t:t['utility']['required'].append(None)),
                    ('invalid-intermediate',lambda t:t['utility']['intermediate'].append(None)),
                    ('unsupported-constraint',lambda t:t['constraints'].append({'id':'future','intent':t['intents'][0]['id'],'metric':'future'})),
                    ('unsupported-output',lambda t:t['utility']['required'][0].update(profile='future')),
                    ('bad-output-reference',lambda t:t['utility']['required'][0].update(observation={'source':'missing','pointer':'/0'}))]:
    owner=json.loads(task);change(owner)
    rows.append({'name':name,'response':w['evaluate'](w['compact'](owner,True),sources)})
# Genuine passes at the exact quantity boundary, including decimal wire forms.
import hashlib
for index,quantity in enumerate([0,17.0,-0.0,2**53-1,2**53,2**64-1]):
    owner=json.loads(task);source={key:json.loads(value) for key,value in sources.items()}
    item=owner['utility']['required'][0];doc=item['expected_document']
    doc['rows']=[{'sku':'quantity-control','available':0,'forecast':quantity}]
    answer={'sku':'quantity-control','units':quantity};item['expected_answer']=answer
    ref=item['observation'];observation=source[ref['source']]
    for part in ref['pointer'].split('/')[1:]:observation=observation[int(part)] if isinstance(observation,list) else observation[part]
    observation.pop('recordedAnswer',None);observation.pop('scriptedAnswer',None)
    observation.update(responseUtf8=json.dumps(doc),recordedAnswer=answer)
    updated={key:w['compact'](value,True) for key,value in source.items()}
    owner['sources']={key:hashlib.sha256(value).hexdigest() for key,value in updated.items()}
    response=w['evaluate'](w['compact'](owner,True),updated)
    assert response['report']['utility']['required'][0]['status']=='passed'
    rows.append({'name':'exact-quantity-'+str(index),'response':response})
for status in ['failed','rejected']:
    response=w['evaluate'](task,sources)
    response['report']={'format':'agent-crash-lab/report-v1','invocation':{'status':status,'code':'test','message':'No financial conclusion'}}
    rows.append({'name':status,'response':response})
for row in rows: row['gate']=w['gate'](row['response']['report'])
print(json.dumps(rows))
`;
const python=spawnSync(process.env.PYTHON||'python',['-I','-S','-c',corpusProgram],
 {cwd:__dirname,encoding:'utf8',maxBuffer:16*1024*1024});
assert.equal(python.status,0,python.stderr);
const corpus=JSON.parse(python.stdout),clone=value=>JSON.parse(JSON.stringify(value));
for(const {name,response} of corpus){
 const before=JSON.stringify(response);
 try{assert.equal(validate(response),response);}catch(error){throw Error(name+' · '+error.cause,{cause:error});}
 assert.equal(JSON.stringify(response),before,name+' must remain unchanged');
}
const base=corpus.find(row=>row.name==='legitimate-installments').response;
const recovery=corpus.find(row=>row.response.report.constraints?.some(c=>c.metric==='principal_recovery'&&c.parents.length)).response;
let rejected=0;
function rejects(name,edit,original=base){
 const response=clone(original);edit(response);
 assert.throws(()=>validate(response),error=>error.message==='The result contains invalid data. Please try again.'
  &&String(error.cause).startsWith('report-contract: '),name);
 rejected++;
}
for(const value of [null,false,7,'report',[]])rejects('envelope '+JSON.stringify(value),d=>{d.report=value;});
for(const key of ['mode','coreVersion','coreSha256','elapsedMs','liveModel','networkTransactions'])
 rejects('missing execution '+key,d=>{delete d.execution[key];});
for(const value of [-1,null,'2',true,Infinity,NaN])rejects('elapsed time '+value,d=>{d.execution.elapsedMs=value;});
rejects('uppercase digest',d=>{d.execution.coreSha256='A'.repeat(64);});
rejects('unsupported mode',d=>{d.execution.mode='fabricated';});
rejects('engine version mismatch',d=>{d.report.invocation.version='future';});
rejects('live model claim',d=>{d.execution.liveModel=true;});
rejects('transaction claim',d=>{d.execution.networkTransactions=1;});
for(const key of ['format','invocation','authority','scope','sources','inventory','coverage','constraints','native_facts','diagnostics','utility'])
 rejects('missing report '+key,d=>{delete d.report[key];});
for(const key of ['run_id','chain_id','protocol_version','closed_horizon','horizon_note','capture'])
 rejects('missing scope '+key,d=>{delete d.report.scope[key];});
rejects('unbound capture',d=>{d.report.scope.capture.source='unlisted';});
rejects('open complete scope',d=>{d.report.scope.closed_horizon=false;});
for(const key of ['rpc_records','send_observations','declared_attempts','observed_transaction_hashes','selected_required_utility','selected_intermediate_utility'])
 for(const value of [-1,1.5,'0',null,Number.MAX_SAFE_INTEGER+1])
  rejects('invalid inventory '+key+' '+value,d=>{d.report.inventory[key]=value;});
rejects('required count drift',d=>{d.report.inventory.selected_required_utility++;});
rejects('intermediate count drift',d=>{d.report.inventory.selected_intermediate_utility++;});
rejects('coverage drift',d=>{d.report.coverage.all_required_utility_assessed=false;});
for(const value of [null,7,'unknown',{}])rejects('intermediate row '+value,d=>{
 d.report.utility.intermediate=[value];d.report.inventory.selected_intermediate_utility=1;
});
for(const row of [{role:'permitted_intermediate'},
 {role:'permitted_intermediate',ref:{source:'recording',pointer:'/0'},status:'unknown'},
 {role:'permitted_intermediate',ref:{source:'recording',pointer:'/0'},status:'observed'},
 {role:'permitted_intermediate',ref:null,status:'observed',observed_status:200,observed_answer_present:false,observed_answer:null}])
 rejects('incomplete intermediate '+JSON.stringify(row),d=>{
  d.report.utility.intermediate=[row];d.report.inventory.selected_intermediate_utility=1;
 });
for(const key of ['id','attempt_id','tx_hash','receipt_id','action_type','from','to','action_index','intent','role','execution_state','finality','provenance','self','requested_yocto','committed_yocto','action_ref','outcome_ref'])
 rejects('missing fact '+key,d=>{delete d.report.native_facts[0][key];});
rejects('duplicate fact',d=>{d.report.native_facts.push(clone(d.report.native_facts[0]));});
rejects('false committed amount',d=>{d.report.native_facts.find(f=>f.execution_state==='committed').committed_yocto='7';});
rejects('false finality',d=>{d.report.native_facts.find(f=>f.execution_state==='committed').finality='unresolved';});
for(const value of ['-1','01','1.0','1e9','',null,true,1,(2n**256n).toString()])
 rejects('invalid cap '+value,d=>{d.report.constraints.find(c=>c.metric==='merchant_gross_principal').cap=value;});
for(const key of ['known_subtotal','exact_total','lower_excess','exact_excess'])
 rejects('incorrect arithmetic '+key,d=>{d.report.constraints.find(c=>c.metric==='merchant_gross_principal')[key]='7';});
rejects('wrong verdict',d=>{d.report.constraints[0].status='breached';});
rejects('missing witnesses',d=>{d.report.constraints.find(c=>c.metric==='merchant_gross_principal').witnesses=[];});
rejects('unknown witness',d=>{d.report.constraints[0].witnesses=['missing'];});
rejects('duplicate diagnostic',d=>{
 const diagnostic={id:'d-test',scope:'test',category:'test',message:'Test issue'};
 d.report.diagnostics.push(diagnostic,clone(diagnostic));
});
rejects('unknown diagnostic link',d=>{d.report.utility.required[0].diagnostic_ids=['missing'];});
for(const key of ['observed_answer_present','observed_answer','observed_status_present','observed_status','reference_check','response_sha256','content_check','answer_check','context_check','observation_ref'])
 rejects('unsupported passed output '+key,d=>{delete d.report.utility.required[0][key];});
rejects('wrong passed answer',d=>{d.report.utility.required[0].answer_check=false;});
rejects('wrong passed profile',d=>{d.report.utility.required[0].profile='future';});
rejects('contradictory passed HTTP check',d=>{d.report.utility.required[0].status_check=false;});
for(const answer of [null,true,7,'answer',[],{}, {sku:'C03'}, {units:17}, {sku:'',units:17},
 {sku:'C03',units:true}, {sku:'C03',units:-1}, {sku:'C03',units:1.5},
 {sku:'C03',units:Number.MAX_SAFE_INTEGER+1}, {sku:'C03',units:'17'}, {sku:'C03',units:17,extra:true}])
 rejects('invalid passed answer '+JSON.stringify(answer),d=>{d.report.utility.required[0].observed_answer=answer;});
const exact=(sign,digits,exponent)=>({exact_json_number:{sign,digits,exponent}});
for(const units of [exact(true,'17',0),exact(0,'',0),exact(0,'17','0'),exact(0,'17',0.5),
 exact(0,'17',-1),exact(1,'17',0),exact(0,'18446744073709551616',0),exact(0,'1',1025),
 {exact_json_number:{sign:0,digits:'17',exponent:0,extra:0}},
 {exact_json_number:{sign:0,digits:'17',exponent:0},extra:0}])
 rejects('invalid exact quantity '+JSON.stringify(units),d=>{d.report.utility.required[0].observed_answer={sku:'C03',units};});
rejects('duplicate resolved output',d=>{
 d.report.utility.required.push(clone(d.report.utility.required[0]));d.report.inventory.selected_required_utility++;
});
rejects('passed without recorded answer',d=>{d.report.utility.required[0].observed_answer_present=false;});
rejects('recovery missing parents',d=>{delete d.report.constraints.find(c=>c.metric==='principal_recovery').parents;},recovery);
rejects('recovery false recovered total',d=>{d.report.constraints.find(c=>c.metric==='principal_recovery'&&c.parents.length).parents[0].successful_allowed_yocto='7';},recovery);
rejects('recovery false failed refund',d=>{
 const c=d.report.constraints.find(c=>c.metric==='principal_recovery'&&c.parents.length);
 c.parents[0].failed_refund_facts=c.parents[0].refund_facts.slice();
},recovery);
// Deterministic arithmetic/property samples. No external service or randomness.
for(let i=1;i<=128;i++){
 rejects('subtotal witness property '+i,d=>{
  const c=d.report.constraints.find(c=>c.metric==='merchant_gross_principal');
  c.known_subtotal=(BigInt(c.known_subtotal)+BigInt(i)).toString();
  c.exact_total=c.known_subtotal;
  const excess=BigInt(c.known_subtotal)>BigInt(c.cap)?BigInt(c.known_subtotal)-BigInt(c.cap):0n;
  c.lower_excess=c.exact_excess=excess.toString();c.status=excess?'breached':'within';
 });
}


// The downloadable input and displayed CI expectation must use the CLI's gate.
const gateStart=source.indexOf('function reportGate(report){');
const gateEnd=source.indexOf('// End CI gate.',gateStart);
assert(gateStart>=0&&gateEnd>gateStart);
const uiGate=vm.runInNewContext('('+source.slice(gateStart,gateEnd)+')');
const gateCases=JSON.parse(python.stdout);
for(const row of gateCases)assert.equal(uiGate(row.response.report),row.gate,row.name);
console.log(JSON.stringify({genuineAndUnknownControls:corpus.length,rejectedMutations:rejected,unchanged:true,ciGateComparisons:gateCases.length}));
