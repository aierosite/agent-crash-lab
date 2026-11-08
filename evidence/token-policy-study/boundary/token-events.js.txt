'use strict';
// Validate embedded event JSON before interpreting it. JSON.parse alone silently
// discards duplicate object members; integer metadata must not lose precision.
function tokenEventJSON(text){
 let at=0,nodes=0;
 const bad=()=>{throw Error('Uninterpretable token event');};
 const space=()=>{while(/[\x20\t\r\n]/.test(text[at]??'')&&at<text.length)at++;};
 const string=()=>{
  const pattern=/"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/y;
  pattern.lastIndex=at;const match=pattern.exec(text);if(!match)bad();at=pattern.lastIndex;
  const value=JSON.parse(match[0]);
  for(let i=0;i<value.length;i++){const n=value.charCodeAt(i);if(n>=0xd800&&n<=0xdbff){const next=value.charCodeAt(++i);if(!(next>=0xdc00&&next<=0xdfff))bad();}else if(n>=0xdc00&&n<=0xdfff)bad();}
  return value;
 };
 const read=depth=>{
  if(depth>64||++nodes>120000)bad();space();const head=text[at];
  if(head==='"')return string();
  if(head==='{'){
   at++;space();const value=Object.create(null),keys=new Set();if(text[at]==='}'){at++;return value;}
   for(;;){if(++nodes>120000||depth+1>64)bad();const key=string();if(keys.has(key))bad();keys.add(key);space();if(text[at++]!==':')bad();value[key]=read(depth+1);space();const end=text[at++];if(end==='}')return value;if(end!==',')bad();space();}
  }
  if(head==='['){
   at++;space();const value=[];if(text[at]===']'){at++;return value;}
   for(;;){value.push(read(depth+1));space();const end=text[at++];if(end===']')return value;if(end!==',')bad();}
  }
  for(const [literal,value] of [['true',true],['false',false],['null',null]])if(text.startsWith(literal,at)){at+=literal.length;return value;}
  const pattern=/-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/y;pattern.lastIndex=at;const match=pattern.exec(text);if(!match||/[.eE]/.test(match[0])||match[0].replace('-','').length>4300)bad();at=pattern.lastIndex;return BigInt(match[0]);
 };
 const value=read(0);space();if(at!==text.length)bad();return value;
}
function projectedTokenEvents(step,contract,vault){
 const events=[];let understood=true,ignored=0;
 const account=x=>typeof x==='string'&&x.length>=2&&x.length<=64&&/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/.test(x);
 const amount=x=>typeof x==='string'&&/^(0|[1-9][0-9]{0,38})$/.test(x)&&BigInt(x)<2n**128n;
 for(const tx of step.transactions){
  const t=tx.result,rows=[t.transaction_outcome,...t.receipts_outcome];
  for(let ni=0;ni<rows.length;ni++){
   const row=rows[ni],o=row.outcome,success=['SuccessValue','SuccessReceiptId'].some(k=>k in o.status);
   for(let li=0;li<o.logs.length;li++){
    const line=o.logs[li];if(!line.startsWith('EVENT_JSON:'))continue;
    if(o.executor_id!==contract||!success){ignored++;continue;}
    let event;try{event=tokenEventJSON(line.slice(11));}catch{understood=false;continue;}
    if(!event||Array.isArray(event)||typeof event!=='object'||typeof event.standard!=='string'){understood=false;continue;}
    if(event.standard!=='nep141')continue;
    if(event.version!=='1.0.0'||!['ft_transfer','ft_mint','ft_burn'].includes(event.event)||!Array.isArray(event.data)||!event.data.length||event.data.length>1024){understood=false;continue;}
    for(let di=0;di<event.data.length;di++){
     const d=event.data[di],kind=event.event;
     if(!d||Array.isArray(d)||typeof d!=='object'||!amount(d.amount)){understood=false;continue;}
     const old=kind==='ft_mint'?null:kind==='ft_burn'?d.owner_id:d.old_owner_id,newOwner=kind==='ft_burn'?null:kind==='ft_mint'?d.owner_id:d.new_owner_id;
     if((old!==null&&!account(old))||(newOwner!==null&&!account(newOwner))){understood=false;continue;}
     if(old===vault||newOwner===vault)events.push({kind,amount:d.amount,old_owner_id:old,new_owner_id:newOwner,receipt_id:row.id,transaction_id:t.transaction.hash,log_index:li,data_index:di,source_pointer:tx.source_pointer+(ni===0?'/transaction_outcome':'/receipts_outcome/'+(ni-1))+'/outcome/logs/'+li,executor_id:o.executor_id});
    }
   }
  }
 }
 return {events,understood,ignored};
}
