//! Owned unsigned receipt research. No signer, access keys, transaction objects or RPC.
use std::{collections::{BTreeMap,HashSet}, fs::{File,OpenOptions}, io::{self,Read,Write}, path::Path, sync::{Arc,atomic::AtomicUsize}};
use near_chain_configs::{Genesis,GenesisConfig,GenesisRecords};
use near_crypto::{KeyType,PublicKey};
use near_parameters::{RuntimeConfig,RuntimeConfigStore,ActionCosts};
use near_primitives::{
    account::{Account,AccountContract}, action::{Action,FunctionCallAction},
    bandwidth_scheduler::BlockBandwidthRequests,
    congestion_info::{BlockCongestionInfo,ExtendedCongestionInfo},
    errors::EpochError, hash::{hash,CryptoHash}, receipt::{Receipt,ReceiptV0,ReceiptEnum,ActionReceipt},
    shard_layout::{ShardLayout,ShardUId},state_record::StateRecord,trie_key::TrieKey,
    types::{AccountId,AccountInfo,Balance,EpochId,EpochInfoProvider},version::PROTOCOL_VERSION,
    views::ExecutionOutcomeView,
};
use near_primitives_core::{apply::ApplyChunkReason,types::Gas};
use near_store::{ShardTries,TrieAccess,genesis::GenesisStateApplier,test_utils::TestTriesBuilder,trie::AccessOptions};
use near_vm_runner::ContractCode;
use node_runtime::{Runtime,ApplyState,SignedValidPeriodTransactions};
use serde::Deserialize;
use serde_json::{json,Value};

#[derive(Deserialize)] #[serde(deny_unknown_fields)]
struct AccountInput {id:String,balance:String,locked:String}
#[derive(Deserialize)] #[serde(deny_unknown_fields)]
struct Call {label:String,method:String,args_utf8:String,predecessor:String,signer:String,deposit:String,gas:u64,round_limit:Option<u32>}
#[derive(Deserialize)] #[serde(deny_unknown_fields)]
struct Case {id:String,wasm_path:String,current:String,validator:String,accounts:Vec<AccountInput>,observe:Vec<String>,keys_hex:Vec<String>,gas_price:String,max_rounds:u32,calls:Vec<Call>}
#[derive(Deserialize)] #[serde(deny_unknown_fields)]
struct Input {cases:Vec<Case>}
struct PausePoint {case:String,step:usize,round:u32}
impl PausePoint {
    fn parse(raw:&str)->Result<Self,Box<dyn std::error::Error>>{
        let parts:Vec<_>=raw.split(':').collect();
        if parts.len()!=3 || parts[0].len()>128 || !parts[0].bytes().all(|b|b.is_ascii_alphanumeric() || b==b'-'){return Err("Expected case:step:round research pause point".into())}
        let step:usize=parts[1].parse()?;let round:u32=parts[2].parse()?;
        if step>=20 || round>=40{return Err("Pause point exceeds research bounds".into())}
        Ok(Self{case:parts[0].into(),step,round})
    }
}
struct Journal {file:File,sequence:u64,pause_after:Option<PausePoint>}
impl Journal {
    fn new(name:&str,pause_after:Option<PausePoint>)->Result<Self,Box<dyn std::error::Error>>{
        let path=Path::new(name);let root=std::env::current_dir()?.canonicalize()?;
        let parent=path.parent().ok_or("Journal parent directory required")?.canonicalize()?;
        if !parent.starts_with(&root){return Err("Journal must stay inside the owned run directory".into())}
        let file=OpenOptions::new().write(true).create_new(true).open(parent.join(path.file_name().ok_or("Journal filename required")?))?;
        Ok(Self{file,sequence:0,pause_after})
    }
    fn pause_if_requested(&mut self,case:&str,step:usize,round:u32)->Result<(),Box<dyn std::error::Error>>{
        if self.pause_after.as_ref().is_some_and(|p|p.case==case && p.step==step && p.round==round){
            // Research-only cooperative fault point. Parent kills this owned process.
            // This tests flushed-journal survival, not persistent node/DB restart.
            self.emit("research_fault_checkpoint",&json!({"case":case,"step":step,"round":round,"mode":"sync_data_then_cooperative_pause_for_external_sigkill"}))?;
            eprintln!("RESEARCH_PAUSE {case}:{step}:{round}");io::stderr().flush()?;
            loop{std::thread::park();}
        }
        Ok(())
    }
    fn emit(&mut self,event:&str,data:&Value)->Result<(),Box<dyn std::error::Error>>{
        let raw=serde_json::to_vec(&json!({"sequence":self.sequence,"event":event,"data":data}))?;
        self.file.write_all(&raw)?;self.file.write_all(b"\n")?;self.file.sync_data()?;self.sequence+=1;Ok(())
    }
}
struct Epoch {layout:ShardLayout,validator:AccountId,stake:Balance}
impl EpochInfoProvider for Epoch {
    fn validator_stake(&self,_:&EpochId,id:&AccountId)->Result<Option<Balance>,EpochError>{Ok(if id==&self.validator{Some(self.stake)}else{None})}
    fn validator_total_stake(&self,_:&EpochId)->Result<Balance,EpochError>{Ok(self.stake)}
    fn minimum_stake(&self,_:&CryptoHash)->Result<Balance,EpochError>{Ok(Balance::ZERO)}
    fn chain_id(&self)->String{"localnet".into()}
    fn shard_layout(&self,_:&EpochId)->Result<ShardLayout,EpochError>{Ok(self.layout.clone())}
}
fn hex(raw:&[u8])->String{raw.iter().map(|x|format!("{x:02x}")).collect()}
fn unhex(s:&str)->Result<Vec<u8>,Box<dyn std::error::Error>>{
    if s.len()%2!=0 || s.len()>2048 || !s.bytes().all(|b|b.is_ascii_hexdigit()){return Err("Invalid observed key hex".into())}
    (0..s.len()).step_by(2).map(|i|Ok(u8::from_str_radix(&s[i..i+2],16)?)).collect()
}
fn describe(config:&RuntimeConfig)->Value{
    let mut costs=BTreeMap::new();
    for (name,cost) in [("new_action_receipt",ActionCosts::new_action_receipt),("function_call_base",ActionCosts::function_call_base),("function_call_byte",ActionCosts::function_call_byte),("transfer",ActionCosts::transfer)] {
        costs.insert(name,config.fees.fee(cost).exec_fee().gas.as_gas().to_string());
    }
    json!({"protocol":PROTOCOL_VERSION,"vm_kind":format!("{:?}",config.wasm_config.vm_kind),"min_gas_purchase_price":config.min_gas_purchase_price.as_yoctonear().to_string(),"execution_gas_costs":costs,
        "runtime_config_debug":format!("{config:?}")})
}
fn snapshot(tries:&ShardTries,uid:ShardUId,root:CryptoHash,spec:&Case)->Result<Value,Box<dyn std::error::Error>>{
    let trie=tries.get_trie_for_shard(uid,root);let access:&dyn TrieAccess=&trie;
    let mut accounts=BTreeMap::new();
    for name in &spec.observe {
        let id:AccountId=name.parse()?;
        let account=near_store::get_account(access,&id)?;
        let row=account.map(|a|json!({"amount":a.amount().as_yoctonear().to_string(),"locked":a.locked().as_yoctonear().to_string(),"storage_usage":a.storage_usage(),"contract":format!("{:?}",a.contract())}));
        accounts.insert(name,row);
    }
    let mut data=BTreeMap::new();
    for key in &spec.keys_hex {
        let v=access.get(&TrieKey::ContractData{account_id:spec.current.parse()?,key:unhex(key)?},AccessOptions::NO_SIDE_EFFECTS)?;
        data.insert(key,v.map(|v|hex(&v)));
    }
    Ok(json!({"state_root":root.to_string(),"accounts":accounts,"contract_data_hex":data}))
}
fn run_case(spec:&Case,config:Arc<RuntimeConfig>,journal:&mut Journal)->Result<Value,Box<dyn std::error::Error>>{
    if spec.max_rounds==0 || spec.max_rounds>40 || spec.calls.len()>20 || spec.accounts.len()>12 || spec.observe.len()>16{return Err("Research case bound exceeded".into())}
    let fixture_dir=Path::new("fixtures").canonicalize()?;let path=Path::new(&spec.wasm_path).canonicalize()?;
    if !path.starts_with(&fixture_dir){return Err("Wasm must be inside owned fixtures".into())}
    let wasm=std::fs::read(&path)?;if wasm.len()>4_194_304 || !wasm.starts_with(b"\0asm"){return Err("Expected bounded Wasm".into())}
    let code=ContractCode::new(wasm.clone(),None);let code_hash=*code.hash();let current:AccountId=spec.current.parse()?;
    let price=Balance::from_yoctonear(spec.gas_price.parse()?);
    if price==Balance::ZERO || price<config.min_gas_purchase_price{return Err("Priced receipt gas must meet configured minimum".into())}
    let layout=ShardLayout::single_shard();let uid=layout.shard_uids().next().unwrap();
    let tries=TestTriesBuilder::new().with_shard_layout(layout.clone()).build();
    let mut records=Vec::new();let mut ids=HashSet::new();let mut supply=Balance::ZERO;let validator:AccountId=spec.validator.parse()?;let mut stake=Balance::ZERO;
    for a in &spec.accounts {
        let id:AccountId=a.id.parse()?;if !ids.insert(id.clone()){return Err("Duplicate fixture account".into())}
        let amount=Balance::from_yoctonear(a.balance.parse()?);let locked=Balance::from_yoctonear(a.locked.parse()?);supply=supply.checked_add(amount).and_then(|n|n.checked_add(locked)).ok_or("Supply overflow")?;
        if id==validator {stake=locked;}else if locked!=Balance::ZERO{return Err("Only the declared fixture validator may have stake".into())}
        let contract=if id==current {AccountContract::Local(code_hash)}else{AccountContract::None};
        records.push(StateRecord::Account{account_id:id,account:Account::new(amount,locked,contract,0)});
    }
    if !ids.contains(&current){return Err("Missing target account".into())}
    if stake==Balance::ZERO || validator==current{return Err("A separate staked fixture validator is required".into())}
    records.push(StateRecord::Contract{account_id:current.clone(),code:wasm});
    // Public test constant from the pinned upstream genesis validation tests.
    // No private key, Signer, keypair generation or access-key state is created.
    let validator_public_key:PublicKey="ed25519:KuTCtARNzxZQ3YvXDeLjx83FDqxv2SdQTSbiq876zR7".parse()?;
    let genesis=Genesis::new(GenesisConfig{validators:vec![AccountInfo{account_id:validator.clone(),public_key:validator_public_key.clone(),amount:stake}],total_supply:supply,epoch_length:60,shard_layout:layout.clone(),protocol_version:PROTOCOL_VERSION,..Default::default()},GenesisRecords(records))?;
    let mut root=GenesisStateApplier::apply(&AtomicUsize::new(0),tries.clone(),uid,&[],&config.fees.storage_usage_config,&genesis,ids);
    let epoch=Epoch{layout,validator:validator.clone(),stake};let runtime=Runtime::new();
    let ci=BlockCongestionInfo::new([(uid.shard_id(),ExtendedCongestionInfo::default())].into_iter().collect());
    let mut state=ApplyState{apply_reason:ApplyChunkReason::UpdateTrackedShard,block_height:1,prev_block_hash:CryptoHash::default(),shard_id:uid.shard_id(),epoch_id:EpochId::default(),epoch_height:0,gas_price:price,block_timestamp:1_000_000_000,gas_limit:None,random_seed:CryptoHash::default(),current_protocol_version:PROTOCOL_VERSION,config:config.clone(),next_wasm_config:None,cache:None,trie_access_tracker_state:Default::default(),is_new_chunk:true,save_receipt_to_tx:false,congestion_info:ci,bandwidth_requests:BlockBandwidthRequests::empty(),on_post_state_ready:None};
    let initial=snapshot(&tries,uid,root,spec)?;let mut steps=Vec::new();
    journal.emit("case_initialized",&json!({"case":spec.id,"code_hash":code_hash.to_string(),"initial":initial}))?;
    for (i,call) in spec.calls.iter().enumerate() {
        if call.gas>300_000_000_000_000 || call.args_utf8.len()>16384{return Err("Call bound exceeded".into())}
        let rounds=call.round_limit.unwrap_or(spec.max_rounds);
        if rounds==0 || rounds>spec.max_rounds{return Err("Invalid per-step receipt horizon".into())}
        let actions=vec![Action::FunctionCall(Box::new(FunctionCallAction{method_name:call.method.clone(),args:call.args_utf8.as_bytes().to_vec(),gas:Gas::from_gas(call.gas),deposit:Balance::from_yoctonear(call.deposit.parse()?)}))];
        let static_exec=node_runtime::config::total_prepaid_exec_fees(&config,&actions,&current)?.gas.checked_add(config.fees.fee(ActionCosts::new_action_receipt).exec_fee().gas).ok_or("Gas overflow")?;
        let prepaid_send=node_runtime::config::total_prepaid_send_fees(&config,&actions)?.gas;
        let attached=node_runtime::config::total_prepaid_gas(&actions)?;
        let budget_gas=static_exec.checked_add(prepaid_send).and_then(|n|n.checked_add(attached)).ok_or("Budget overflow")?;
        let external_budget=u128::from(budget_gas.as_gas()).checked_mul(price.as_yoctonear()).and_then(|n|n.checked_add(call.deposit.parse().ok()?)).ok_or("Credit overflow")?;
        let receipt=Receipt::V0(ReceiptV0{predecessor_id:call.predecessor.parse()?,receiver_id:current.clone(),receipt_id:hash(format!("{}:{i}:{}",spec.id,call.label).as_bytes()),receipt:ReceiptEnum::Action(ActionReceipt{signer_id:call.signer.parse()?,signer_public_key:PublicKey::empty(KeyType::ED25519),gas_price:price,output_data_receivers:vec![],input_data_ids:vec![],actions})});
        let input_receipt=receipt.clone();let before=snapshot(&tries,uid,root,spec)?;let mut pending=vec![receipt];let mut blocks=Vec::new();let mut queued=false;let mut error=None;
        journal.emit("step_begin",&json!({"case":spec.id,"index":i,"label":call.label,"input_receipt":input_receipt,"before":before,"external_incoming_prepaid_credit":external_budget.to_string()}))?;
        for round in 0..rounds {
            if pending.is_empty() && !queued {break}
            let incoming=std::mem::take(&mut pending);
            let transactions=SignedValidPeriodTransactions::new(Vec::new(),Vec::new());assert_eq!(transactions.len(),0);
            let trie=tries.get_trie_for_shard(uid,root);
            journal.emit("block_begin",&json!({"case":spec.id,"step":i,"round":round,"height":state.block_height,"state_root_before":root.to_string(),"incoming":incoming,"signed_transactions":0}))?;
            let applied=match runtime.apply(trie,&None,&state,&incoming,transactions,&epoch,Default::default()) {
                Ok(a)=>a,Err(e)=>{error=Some(format!("{e:?}"));let row=json!({"round":round,"height":state.block_height,"incoming":incoming,"runtime_error":error});journal.emit("block_error",&json!({"case":spec.id,"step":i,"result":row}))?;blocks.push(row);break}
            };
            assert_eq!(applied.stats.transactions_num,0);
            let prior=root;let mut update=tries.store_update();root=tries.apply_all(&applied.trie_changes,uid,&mut update);update.commit();
            let outcomes:Vec<_>=applied.outcomes.iter().map(|o|json!({"id":o.id.to_string(),"outcome":ExecutionOutcomeView::from(o.outcome.clone())})).collect();
            let changes:Vec<_>=applied.state_changes.iter().map(|s|json!({"trie_key_debug":format!("{:?}",s.trie_key),"changes":s.changes.iter().map(|c|json!({"cause_debug":format!("{:?}",c.cause),"data_hex":c.data.as_ref().map(|v|hex(v))})).collect::<Vec<_>>()})).collect();
            let b=&applied.stats.balance;
            let row=json!({"round":round,"height":state.block_height,"state_root_before":prior.to_string(),"state_root_after":root.to_string(),"incoming":incoming,"outgoing":applied.outgoing_receipts,"outcomes":outcomes,"state_changes":changes,"snapshot_after":snapshot(&tries,uid,root,spec)?,
                "balance_stats":{"tx_burnt":b.tx_burnt_amount.as_yoctonear().to_string(),"slashed_burnt":b.slashed_burnt_amount.as_yoctonear().to_string(),"other_burnt":b.other_burnt_amount.as_yoctonear().to_string(),"gas_deficit":b.gas_deficit_amount.as_yoctonear().to_string(),"subsidized":b.subsidized_amount.as_yoctonear().to_string()},"delayed_receipts":applied.delayed_receipts_count,"congestion_receipt_bytes":applied.congestion_info.as_ref().map(|info|info.receipt_bytes().to_string()),"internal_queue_remaining_after":applied.delayed_receipts_count>0 || applied.congestion_info.as_ref().is_some_and(|info|info.receipt_bytes()>0),"signed_transactions":applied.stats.transactions_num});
            journal.emit("block_result",&json!({"case":spec.id,"step":i,"result":row}))?;blocks.push(row);
            journal.pause_if_requested(&spec.id,i,round)?;
            pending=applied.outgoing_receipts;
            queued=applied.delayed_receipts_count>0;
            if let Some(info)=applied.congestion_info {queued|=info.receipt_bytes()>0;state.congestion_info.insert(uid.shard_id(),ExtendedCongestionInfo{missed_chunks_count:0,congestion_info:info});}
            state.bandwidth_requests=BlockBandwidthRequests{shards_bandwidth_requests:[(uid.shard_id(),applied.bandwidth_requests)].into_iter().collect()};
            state.prev_block_hash=hash(format!("{}:{}:{}",spec.id,state.block_height,root).as_bytes());state.block_height+=1;state.block_timestamp+=1_000_000_000;
        }
        let complete=error.is_none() && pending.is_empty() && !queued;
        let row=json!({"index":i,"label":call.label,"input_receipt":input_receipt,"external_incoming_prepaid_credit":external_budget.to_string(),"budget_gas":{"attached":attached.as_gas().to_string(),"prepaid_send":prepaid_send.as_gas().to_string(),"static_execution":static_exec.as_gas().to_string()},"before":before,"blocks":blocks,"after":snapshot(&tries,uid,root,spec)?,"pending_receipts":pending,"internal_queue_remaining":queued,"complete":complete,"runtime_error":error});
        journal.emit("step_result",&json!({"case":spec.id,"result":row}))?;steps.push(row);
        if !complete {break}
    }
    Ok(json!({"id":spec.id,"code_hash":code_hash.to_string(),"initial":initial,"steps_planned":spec.calls.len(),"steps_executed":steps.len(),"steps":steps,"final":snapshot(&tries,uid,root,spec)?,"validator_context":{"account":validator,"public_key":validator_public_key,"stake":stake.as_yoctonear().to_string(),"source":"literal public upstream test field, no private key or signing"},"signed_transactions":0,"access_keys_seeded":0}))
}
fn main()->Result<(),Box<dyn std::error::Error>>{
    let store=RuntimeConfigStore::new(None);let config=store.get_config(PROTOCOL_VERSION).clone();
    let args:Vec<_>=std::env::args().skip(1).collect();
    if args==["--describe"]{println!("{}",describe(&config));return Ok(())}
    if (args.len()!=2 && args.len()!=4) || args[0]!="--journal" || (args.len()==4 && args[2]!="--pause-after"){return Err("Use --describe, or --journal <new file> [--pause-after case:step:round]".into())}
    let pause_after=if args.len()==4 {Some(PausePoint::parse(&args[3])?)}else{None};
    let mut raw=String::new();io::stdin().take(1_048_577).read_to_string(&mut raw)?;if raw.len()>1_048_576{return Err("Input exceeds 1 MiB".into())}
    let input:Input=serde_json::from_str(&raw)?;if input.cases.len()>8{return Err("At most eight research cases".into())}
    if let Some(point)=pause_after.as_ref(){
        let case=input.cases.iter().find(|case|case.id==point.case).ok_or("Pause case not in exact input")?;
        let call=case.calls.get(point.step).ok_or("Pause step not in exact input")?;
        if point.round>=call.round_limit.unwrap_or(case.max_rounds){return Err("Pause round is outside declared horizon".into())}
    }
    let mut journal=Journal::new(&args[1],pause_after)?;journal.emit("run_start",&json!({"raw_input_utf8":raw,"configuration":describe(&config),"signed_transactions":0}))?;
    let mut cases=Vec::new();for case in &input.cases {
        journal.emit("case_begin",&json!({"case":case.id}))?;
        let result=match run_case(case,config.clone(),&mut journal) {Ok(v)=>v,Err(e)=>json!({"id":case.id,"harness_error":e.to_string()})};
        journal.emit("case_result",&result)?;cases.push(result);
    }
    let report=json!({"format":"agent-crash-lab/unsigned-receipt-research-v1","upstream_revision":"bc4e9e8cfb03d9e82f027883055624e18576993e","runtime":"node-runtime Runtime::apply","configuration":describe(&config),"context":"Constructed local genesis and incoming receipts; no authenticated chain history, signer or RPC.","signed_transactions":0,"cases":cases});
    journal.emit("run_complete",&report)?;println!("{}",serde_json::to_string(&report)?);Ok(())
}
