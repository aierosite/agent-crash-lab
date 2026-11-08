"""Separate-process raw-chain audit and original typed reference replay. No inference."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
import copy, json, sys

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from protocol import SPEC, GRAMMAR, pack, decode, initial_messages, render, utc
from original_loader import load_originals
from grade import grade

BASE, ORIGINAL, _, _, _, _ = load_originals()
SUITE = BASE.get_new_version((1, 2, 2))

def bytes_check(record, field, digest):
    raw = record[field].encode('utf-8')
    assert sha256(raw).hexdigest() == record[digest], field
    return raw

def audit_episode(episode, *, scripted=False):
    assert episode.get('resetComplete', scripted), 'No typed initial state'
    env = SUITE.load_and_inject_default_environment({})
    if episode['profile'] == 'role-spoof':
        if episode['task'] == 0:
            env.filesystem.files['bill-december-2023.txt'] += SPEC['rolePayload']
        else:
            next(t for t in env.bank_account.transactions if t.id == 5).subject += SPEC['rolePayload']
    assert env.model_dump() == episode['preState'], 'Initial fixture changed'
    runtime = ORIGINAL.FunctionsRuntime(SUITE.tools)
    sdk_index = 0
    balances = {'payer': 181000, 'bill': 0, 'attacker': 0, 'other': 0}
    for event in episode['hostEvents']:
        assert event['beforeState'] == env.model_dump(), 'Broken typed-state chain'
        request = decode(bytes_check(event, 'requestUtf8', 'requestSha256'), lexical=True)
        bytes_check(event, 'responseUtf8', 'responseSha256')
        name = request.pop('tool')
        assert event['path'] == '/' + name and event['sdkBefore'] == sdk_index
        result = error = None
        if event.get('originalRuntimeInvoked'):
            args = runtime.functions[name].parameters.model_validate(request).model_dump()
            assert args == event['typedArguments'], 'Typed arguments detached from raw request'
            result, error = runtime.run_function(env, name, args)
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            if isinstance(result, list):
                result = [v.model_dump() if hasattr(v, 'model_dump') else v for v in result]
            assert result == event['originalResult'] and error == event['originalError'], 'Original runtime result changed'
        if 'sdkIndex' in event:
            assert name == 'send_money' and event['sdkIndex'] == sdk_index
            row = episode['sdkRows'][sdk_index]
            amount = Fraction(request['amount']) * 100
            assert amount.denominator == 1 and 0 < amount <= 181000
            amount = int(amount)
            receiver = SPEC['recipientMap'][request['recipient'].upper()]
            assert row['amount'] == str(amount) and row['receiver'] == receiver
            assert row['case'] == episode['id'] and row['id'] == episode['id'] + '/' + str(sdk_index)
            assert row['intent'] == 'bill' and row['method'] == 'ft_transfer'
            assert row['args'] == {'receiver_id': receiver, 'amount': str(amount), 'memo': request['subject']}
            key = receiver.removesuffix('.testnet')
            assert int(row['payer_before']) == balances['payer'] and int(row['receiver_before']) == balances[key]
            balances['payer'] -= amount
            balances[key] += amount
            assert int(row['payer_after']) == balances['payer'] and int(row['receiver_after']) == balances[key]
            assert {k: int(v) for k, v in row['balances'].items()} == balances and int(row['supply']) == sum(balances.values()) == 181000
            events = [decode(x.removeprefix('EVENT_JSON:')) for x in row['logs']]
            assert len(events) == 1 and events[0] == {'standard': 'nep141', 'version': '1.0.0', 'event': 'ft_transfer',
                'data': [{'old_owner_id': 'payer.testnet', 'new_owner_id': receiver, 'amount': str(amount), 'memo': request['subject']}]}
            env.bank_account.balance = balances['payer'] / 100
            assert event['balanceProjectionAtomic'] == str(balances['payer'])
            sdk_index += 1
        assert event['sdkAfter'] == sdk_index and event['afterState'] == env.model_dump(), 'Post-state disagrees with typed original replay'
        if event['httpStatus'] == 200:
            reply = decode(event['responseUtf8'])
            if event.get('originalRuntimeInvoked'):
                assert reply['result'] == result and error is None
            else:
                assert name == 'finish' or event.get('recovered'), 'Unexplained successful no-op'
    assert sdk_index == len(episode['sdkRows']) and env.model_dump() == episode['postState']
    if 'sdkSnapshot' in episode:
        snapshot = episode['sdkSnapshot']
        assert snapshot['case'] == episode['id'] and snapshot['op'] == 'snapshot'
        assert {k: int(snapshot[k]) for k in balances} == balances and int(snapshot['supply']) == 181000
    else:
        assert not episode['executionComplete'], 'Closed episode lacks final physical snapshot'
    assert episode['prefetch']['httpStatus'] == 200
    events_by_id = {event['callId']: event for event in episode['hostEvents']}
    assert len(events_by_id) == len(episode['hostEvents']), 'Duplicate host call ID'
    links = [episode['prefetch']] + [s for s in episode['steps'] if 'requestUtf8' in s]
    for link in links:
        bytes_check(link, 'requestUtf8', 'requestSha256')
        bytes_check(link, 'responseUtf8', 'responseSha256')
        host = next(e for e in episode['hostEvents'] if e['requestUtf8'] == link['requestUtf8'] and e['responseUtf8'] == link['responseUtf8'] and e['httpStatus'] == link['httpStatus'])
        assert link['requestUrl'].endswith(host['path'])
    assert len(links) == len(episode['hostEvents']), 'Unlinked host call'
    return grade(episode)

def audit_actual(root):
    lock = decode((H / 'LOCK.json').read_bytes())
    assert all(sha256((H / n).read_bytes()).hexdigest() == m['sha256'] for n, m in lock['sources'].items())
    assert sha256((H / 'REGISTRATION.json').read_bytes()).hexdigest() == lock['registrationSha256']
    plan = decode((H / 'REGISTRATION.json').read_bytes())
    execution = decode((root / 'execution.json').read_bytes())
    assert execution['terminal'] and execution['sourcesUnchanged']
    episodes = decode((root / 'episodes.json').read_bytes())
    calls = decode((root / 'calls.json').read_bytes())
    wire = decode((root / 'sdk-wire.json').read_bytes())
    statuses = decode((root / 'statuses.json').read_bytes())
    assert plan['cases'] == SPEC['cases']
    assert list(statuses) == sorted(c['id'] for c in plan['cases'])  # canonical JSON key order
    assert len(episodes) == execution['startedCases'] and len(calls) == execution['evaluationCalls']
    assert len({e['id'] for e in episodes}) == len(episodes)
    assert [e['id'] for e in episodes] == [c['id'] for c in plan['cases'] if statuses[c['id']]['state'] != 'unstarted']
    assert [c['id'] for c in calls] == list(range(len(calls)))
    by_call = {c['id']: c for c in calls}
    plan_by_id = {c['id']: c for c in plan['cases']}
    used, grades = set(), []
    for episode in episodes:
        assert all(episode[k] == v for k, v in plan_by_id[episode['id']].items())
        report = audit_episode(episode)
        messages = initial_messages(episode['task'], episode['prefetch'])
        assert sha256(messages[2]['content'].encode()).hexdigest() == episode['prefetchMessageSha256']
        assert decode(episode['prefetch']['requestUtf8']) == SPEC['tasks'][str(episode['task'])]['prefetch']
        for step in episode['steps']:
            call = by_call[step['modelCallId']]
            assert call['id'] not in used and call['case'] == episode['id'] and call['turn'] == step['turn']
            used.add(call['id'])
            raw = bytes_check(call, 'wireRequestUtf8', 'requestSha256')
            expected = {'prompt': render(messages), 'grammar': GRAMMAR, 'temperature': .2,
                        'seed': episode['seed'], 'n_predict': plan['limits']['generatedTokens'],
                        'cache_prompt': False, 'stop': ['<|im_end|>']}
            assert decode(raw) == expected
            if 'tokenizerResponse' in call:
                token_request = call['tokenizerRequestUtf8'].encode()
                assert decode(token_request) == {'content': expected['prompt'], 'add_special': False, 'parse_special': True}
                token_reply = call['tokenizerResponse']
                assert token_reply['requestSha256'] == sha256(token_request).hexdigest()
                if token_reply.get('httpStatus') == 200:
                    bytes_check(token_reply, 'responseUtf8', 'responseSha256')
                    assert call['promptTokens'] == len(decode(token_reply['responseUtf8'])['tokens'])
            if 'response' not in call or call['response'].get('httpStatus') != 200:
                assert step.get('unexecuted') and 'requestUtf8' not in step
                continue
            reply = call['response']
            assert reply['requestSha256'] == call['requestSha256']
            bytes_check(reply, 'responseUtf8', 'responseSha256')
            returned = decode(reply['responseUtf8'])
            assert returned['content'] == call['content'] == step['rawToolUtf8']
            if 'requestUtf8' not in step:
                assert step.get('unexecuted') or step.get('protocolError')
                continue
            assert step['requestUtf8'] == returned['content']
            assert call['state'] == 'complete' and returned['stop_type'] in ['eos', 'word'] and not returned.get('truncated')
            host = next(e for e in episode['hostEvents'] if str(e['callId']) == str(call['id']))
            for field in ['requestUtf8', 'requestSha256', 'responseUtf8', 'responseSha256', 'httpStatus']:
                assert host[field] == step[field], field
            messages.append({'role': 'assistant', 'content': returned['content']})
            messages.append({'role': 'user', 'content': pack({'http_status': step['httpStatus'], 'response': decode(step['responseUtf8'])}).decode()})
        if episode['executionComplete']:
            assert messages == episode['messages']
        assert statuses[episode['id']]['state'] == ('closed' if episode['executionComplete'] else 'partial')
        grades.append(report)
    assert used == set(by_call), 'Missing or unlinked model call'
    pays = [r for r in wire if decode(r['requestUtf8'])['op'] == 'pay']
    physical = [r for e in episodes for r in e['sdkRows']]
    assert len(pays) == len(physical) == execution['sdkMockPayments']
    assert execution['inferenceRequestsStarted'] == sum(c['inferenceRequestStarted'] for c in calls)
    assert execution['returnedResponses'] == sum(c.get('response', {}).get('httpStatus') == 200 for c in calls)
    assert execution['closedCases'] == sum(s['state'] == 'closed' for s in statuses.values())
    assert execution['partialCases'] == sum(s['state'] == 'partial' for s in statuses.values())
    assert execution['unstartedCases'] == sum(s['state'] == 'unstarted' for s in statuses.values())
    for raw, row in zip(pays, physical):
        assert raw['state'] == 'complete' and decode(raw['responseUtf8']) == row
        request = decode(raw['requestUtf8'])
        assert request == {'op': 'pay', 'case': row['case'], 'id': row['id'], 'receiver': row['receiver'], 'amount': row['amount'], 'memo': row['args']['memo']}
    return {'atUtc': utc(), 'accepted': True, 'episodes': len(episodes), 'modelCalls': len(calls),
            'sdkMockPayments': len(physical), 'grades': grades,
            'independentBlindEvaluation': False,
            'scope': 'Post-execution same-author auditor independently replays unchanged external typed tools/predicates and checks raw byte links/physical balances. Receipt wrappers remain constructed; no network consensus or broad accuracy proof.'}

if __name__ == '__main__':
    result = audit_actual(H / 'actual')
    (H / 'AUDIT.post-lock.json').write_bytes(pack(result) + b'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'grades'}))
