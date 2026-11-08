//! Local host-mock study. No NEAR node, wallet or transaction client.
use near_contract_standards::fungible_token::{
    core::FungibleTokenCore, resolver::FungibleTokenResolver, FungibleToken,
};
use near_sdk::{
    AccountId, NearToken, PromiseResult, json_types::U128, mock::with_mocked_blockchain,
    serde::{Deserialize, Serialize}, serde_json::{self, json},
    test_utils::{VMContextBuilder, get_created_receipts, get_logs}, testing_env,
};
use std::{collections::HashMap, io::{self, Read}};

#[derive(Deserialize, Serialize)]
#[serde(crate = "near_sdk::serde")]
struct Case {
    id: String,
    amount: String,
    receiver_balance: String,
    sender_registered: bool,
    hook_result: Option<Vec<u8>>,
}

fn execute(case: &Case) -> serde_json::Value {
    let payer: AccountId = "payer.testnet".parse().unwrap();
    let receiver: AccountId = "payee.testnet".parse().unwrap();
    let token_id: AccountId = "token.testnet".parse().unwrap();
    let sink: AccountId = "sink.testnet".parse().unwrap();
    let amount: u128 = case.amount.parse().unwrap();
    let receiver_balance: u128 = case.receiver_balance.parse().unwrap();
    assert!(amount > 0 && receiver_balance <= amount);

    // Clear the prior case's mocked trie. Subsequent contexts retain this case's state.
    with_mocked_blockchain(|b| { b.take_storage(); });
    let mut context = VMContextBuilder::new();
    context.current_account_id(token_id.clone()).signer_account_id(payer.clone())
        .predecessor_account_id(payer.clone()).attached_deposit(NearToken::from_yoctonear(1));
    testing_env!(context.build());
    let mut token = FungibleToken::new(b"study".to_vec());
    token.internal_register_account(&payer);
    token.internal_register_account(&receiver);
    token.internal_register_account(&sink);
    token.internal_deposit(&payer, amount);
    let promise = token.ft_transfer_call(receiver.clone(), U128(amount), None, "study".into());
    drop(promise);
    let initial_logs = get_logs();
    let created = get_created_receipts().into_iter().map(|r| json!({
        "receiver_id": r.receiver_id,
        "receipt_indices": r.receipt_indices,
        "actions": r.actions,
    })).collect::<Vec<_>>();

    // Inject registered balance/registration preconditions. These are not executed
    // receiver actions and are not advertised as a chain or full contract trace.
    token.accounts.insert(&receiver, &receiver_balance);
    token.accounts.insert(&sink, &(amount - receiver_balance));
    if !case.sender_registered { token.accounts.remove(&payer); }
    let before = json!({
        "payer": token.accounts.get(&payer).map(|n| n.to_string()),
        "receiver": token.accounts.get(&receiver).map(|n| n.to_string()),
        "sink": token.accounts.get(&sink).map(|n| n.to_string()),
        "supply": token.total_supply.to_string(),
    });
    context.predecessor_account_id(token_id).attached_deposit(NearToken::from_yoctonear(0));
    let result = match &case.hook_result {
        Some(bytes) => PromiseResult::Successful(bytes.clone()),
        None => PromiseResult::Failed,
    };
    testing_env!(context.build(), near_sdk::test_vm_config(), near_sdk::RuntimeFeesConfig::test(),
        HashMap::default(), vec![result]);
    let used = token.ft_resolve_transfer(payer.clone(), receiver.clone(), U128(amount));
    json!({
        "format": "agent-crash-lab/sdk-resolver-observation-v1",
        "sdk_revision": "bacd081a0bd648d840b814dab7677e1f3330afbb",
        "case": case,
        "initial_logs": initial_logs,
        "created_mock_receipts": created,
        "ledger_before": before,
        "resolver_return": used.0.to_string(),
        "resolver_logs": get_logs(),
        "ledger_after": {
            "payer": token.accounts.get(&payer).map(|n| n.to_string()),
            "receiver": token.accounts.get(&receiver).map(|n| n.to_string()),
            "sink": token.accounts.get(&sink).map(|n| n.to_string()),
            "supply": token.total_supply.to_string(),
        },
        "scope": "Unmodified official SDK methods, mock host and injected preconditions. Not network/consensus/WASM/agent execution.",
    })
}

fn main() {
    let mut raw = String::new();
    io::stdin().read_to_string(&mut raw).unwrap();
    let cases: Vec<Case> = serde_json::from_str(&raw).unwrap();
    let observed = cases.iter().map(execute).collect::<Vec<_>>();
    println!("{}", serde_json::to_string(&observed).unwrap());
}
