//! Mock ledger process. Direct SDK methods; no node, keys or network transaction.
use near_contract_standards::fungible_token::{FungibleToken, core::FungibleTokenCore};
use near_sdk::{AccountId, NearToken, json_types::U128, mock::with_mocked_blockchain,
    serde_json::{self, json}, test_utils::{VMContextBuilder, get_created_receipts, get_logs}, testing_env};
use std::io::{self, BufRead, Write};

fn context() {
    let mut builder = VMContextBuilder::new();
    builder.current_account_id("token.testnet".parse().unwrap())
        .signer_account_id("payer.testnet".parse().unwrap())
        .predecessor_account_id("payer.testnet".parse().unwrap())
        .attached_deposit(NearToken::from_yoctonear(1));
    testing_env!(builder.build());
}

fn main() {
    let payer: AccountId = "payer.testnet".parse().unwrap();
    let merchant: AccountId = "merchant.testnet".parse().unwrap();
    let mut token: Option<FungibleToken> = None;
    let mut case_id = String::new();
    for line in io::stdin().lock().lines() {
        let request: serde_json::Value = serde_json::from_str(&line.unwrap()).unwrap();
        let op = request["op"].as_str().unwrap();
        let result = if op == "reset" {
            with_mocked_blockchain(|b| { b.take_storage(); });
            context();
            let mut fresh = FungibleToken::new(b"agent-loop".to_vec());
            fresh.internal_register_account(&payer);
            fresh.internal_register_account(&merchant);
            fresh.internal_deposit(&payer, 1_000_000);
            token = Some(fresh);
            case_id = request["case"].as_str().unwrap().to_string();
            json!({"op":"reset", "case":case_id, "funding":"1000000", "new_transactions":0})
        } else {
            assert_eq!(request["case"].as_str().unwrap(), case_id);
            let state = token.as_mut().expect("reset first");
            if op == "pay" {
                let amount: u128 = request["amount"].as_str().unwrap().parse().unwrap();
                let intent = request["intent"].as_str().unwrap();
                assert!(amount > 0 && amount <= 1000 && matches!(intent, "A" | "B"));
                context();
                let before = state.ft_balance_of(payer.clone()).0;
                let merchant_before = state.ft_balance_of(merchant.clone()).0;
                let memo = format!("invoice:{intent}");
                state.ft_transfer(merchant.clone(), U128(amount), Some(memo.clone()));
                let after = state.ft_balance_of(payer.clone()).0;
                let merchant_after = state.ft_balance_of(merchant.clone()).0;
                assert_eq!(before - after, amount);
                assert_eq!(merchant_after - merchant_before, amount);
                assert!(get_created_receipts().is_empty());
                json!({"op":"pay", "case":case_id, "id":request["id"], "intent":intent,
                    "amount":amount.to_string(), "method":"ft_transfer",
                    "args":{"receiver_id":merchant,"amount":amount.to_string(),"memo":memo},
                    "payer_before":before.to_string(), "payer_after":after.to_string(),
                    "merchant_before":merchant_before.to_string(), "merchant_after":merchant_after.to_string(),
                    "supply":state.ft_total_supply().0.to_string(), "logs":get_logs(),
                    "created_mock_receipts":0, "new_transactions":0})
            } else {
                assert_eq!(op, "snapshot");
                json!({"op":"snapshot", "case":case_id, "payer":state.ft_balance_of(payer.clone()).0.to_string(),
                    "merchant":state.ft_balance_of(merchant.clone()).0.to_string(), "supply":state.ft_total_supply().0.to_string()})
            }
        };
        println!("{}", serde_json::to_string(&result).unwrap());
        io::stdout().flush().unwrap();
    }
}
