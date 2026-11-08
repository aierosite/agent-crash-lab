//! Owned billing study harness: direct canonical SDK calls in a mock host.
//! No node, RPC, key, signature, deployed contract or financial transaction.
use near_contract_standards::fungible_token::{FungibleToken, core::FungibleTokenCore};
use near_sdk::{AccountId, NearToken, json_types::U128, mock::with_mocked_blockchain,
    serde_json::{self, json}, test_utils::{VMContextBuilder, get_created_receipts, get_logs}, testing_env};
use std::io::{self, BufRead, Write};

fn context() {
    let mut b = VMContextBuilder::new();
    b.current_account_id("token.testnet".parse().unwrap())
        .signer_account_id("payer.testnet".parse().unwrap())
        .predecessor_account_id("payer.testnet".parse().unwrap())
        .attached_deposit(NearToken::from_yoctonear(1));
    testing_env!(b.build());
}

fn main() {
    let payer: AccountId = "payer.testnet".parse().unwrap();
    let names = ["bill.testnet", "attacker.testnet", "other.testnet"];
    let mut token: Option<FungibleToken> = None;
    let mut case = String::new();
    for line in io::stdin().lock().lines() {
        let r: serde_json::Value = serde_json::from_str(&line.unwrap()).unwrap();
        let op = r["op"].as_str().unwrap();
        let output = if op == "reset" {
            with_mocked_blockchain(|b| { b.take_storage(); });
            context();
            let mut fresh = FungibleToken::new(b"billing-study".to_vec());
            fresh.internal_register_account(&payer);
            for name in names { fresh.internal_register_account(&name.parse().unwrap()); }
            fresh.internal_deposit(&payer, 181_000);
            token = Some(fresh);
            case = r["case"].as_str().unwrap().to_string();
            json!({"op":"reset","case":case,"funding":"181000","new_transactions":0})
        } else {
            assert_eq!(r["case"].as_str().unwrap(), case);
            let state = token.as_mut().expect("reset before effects");
            if op == "pay" {
                let receiver = r["receiver"].as_str().unwrap();
                assert!(names.contains(&receiver));
                let recipient: AccountId = receiver.parse().unwrap();
                let amount: u128 = r["amount"].as_str().unwrap().parse().unwrap();
                assert!(amount > 0 && amount <= 181_000);
                let memo = r["memo"].as_str().unwrap();
                assert!(memo.len() <= 512);
                context();
                let before = state.ft_balance_of(payer.clone()).0;
                let receiver_before = state.ft_balance_of(recipient.clone()).0;
                assert!(before >= amount);
                state.ft_transfer(recipient.clone(), U128(amount), Some(memo.to_string()));
                let after = state.ft_balance_of(payer.clone()).0;
                let receiver_after = state.ft_balance_of(recipient.clone()).0;
                assert_eq!(before - after, amount);
                assert_eq!(receiver_after - receiver_before, amount);
                assert!(get_created_receipts().is_empty());
                let balances = json!({"payer":state.ft_balance_of(payer.clone()).0.to_string(),
                    "bill":state.ft_balance_of("bill.testnet".parse().unwrap()).0.to_string(),
                    "attacker":state.ft_balance_of("attacker.testnet".parse().unwrap()).0.to_string(),
                    "other":state.ft_balance_of("other.testnet".parse().unwrap()).0.to_string()});
                json!({"op":"pay","case":case,"id":r["id"],"intent":"bill","method":"ft_transfer",
                    "args":{"receiver_id":recipient,"amount":amount.to_string(),"memo":memo},
                    "amount":amount.to_string(),"receiver":receiver,
                    "payer_before":before.to_string(),"payer_after":after.to_string(),
                    "receiver_before":receiver_before.to_string(),"receiver_after":receiver_after.to_string(),
                    "supply":state.ft_total_supply().0.to_string(),"balances":balances,
                    "logs":get_logs(),"created_mock_receipts":0,"new_transactions":0})
            } else {
                assert_eq!(op, "snapshot");
                json!({"op":"snapshot","case":case,
                    "payer":state.ft_balance_of(payer.clone()).0.to_string(),
                    "bill":state.ft_balance_of("bill.testnet".parse().unwrap()).0.to_string(),
                    "attacker":state.ft_balance_of("attacker.testnet".parse().unwrap()).0.to_string(),
                    "other":state.ft_balance_of("other.testnet".parse().unwrap()).0.to_string(),
                    "supply":state.ft_total_supply().0.to_string()})
            }
        };
        println!("{}",serde_json::to_string(&output).unwrap());
        io::stdout().flush().unwrap();
    }
}
