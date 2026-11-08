"""Prospectively fixed two-model/four-task inference; no resampling or hidden repair."""
from pathlib import Path
from hashlib import sha256, file_digest
import json, subprocess, sys, time, traceback

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from protocol import pack, decode, utc, SPEC, GRAMMAR, render, CaseFailure, GroupFailure, BatchFailure
from bank_server import Bank, serve
from sdk_bridge import Sdk
from driver import drive
from model_client import Model, proxy
from verify_sdk_sources import verify as verify_sdk

def digest(p):
    with p.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()
def save(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(pack(value) + b'\n')
    temp.replace(path)

def main():
    plan = decode((H / 'REGISTRATION.json').read_bytes())
    lock = decode((H / 'LOCK.json').read_bytes())
    out = H / 'actual'
    out.mkdir(exist_ok=False)
    limits = plan['limits']
    start = time.monotonic()
    deadline = start + limits['batchSeconds']
    calls, episodes, groups = [], [], []
    statuses = {c['id']: {'case': c['id'], 'state': 'unstarted'} for c in plan['cases']}
    sdk = server = thread = model = None
    log = None
    error = None
    def unchanged():
        return all(digest(H / n) == v['sha256'] for n, v in lock['sources'].items())
    save(out / 'run.json', {'startedAtUtc': utc(), 'windowsActorPid': __import__('os').getpid(),
                            'registrationSha256': digest(H / 'REGISTRATION.json'), 'lockSha256': digest(H / 'LOCK.json'), 'status': 'started'})
    def checkpoint(episode):
        episodes[-1] = decode(pack(episode))
        save(out / 'episodes.json', episodes)
        save(out / 'sdk-wire.json', sdk.requests)
        save(out / 'statuses.json', statuses)
    def complete(case, turn, messages):
        if time.monotonic() >= deadline or len(calls) >= limits['maxEvaluationCalls']:
            raise BatchFailure('Registered global time/call limit reached')
        prompt = render(messages)
        body = pack({'prompt': prompt, 'grammar': GRAMMAR, 'temperature': .2, 'seed': case['seed'],
                     'n_predict': limits['generatedTokens'], 'cache_prompt': False, 'stop': ['<|im_end|>']})
        row = {'id': len(calls), 'case': case['id'], 'turn': turn, 'startedAtUtc': utc(), 'state': 'started',
               'wireRequestUtf8': body.decode(), 'requestSha256': sha256(body).hexdigest(),
               'inferenceRequestStarted': False, 'warmup': False}
        calls.append(row)
        save(out / 'calls.json', calls)
        try:
            if len(body) > 262144:
                raise CaseFailure('Full request exceeds byte quota', row['id'])
            token_request = pack({'content': prompt, 'add_special': False, 'parse_special': True})
            token_reply = proxy(model.port, 'POST', '/tokenize', token_request, 15)
            row.update(tokenizerRequestUtf8=token_request.decode(), tokenizerResponse=token_reply)
            if token_reply.get('httpStatus') != 200 or token_reply.get('transportError'):
                raise GroupFailure('Owned tokenizer transport failed', row['id'])
            row['promptTokens'] = len(decode(token_reply['responseUtf8'])['tokens'])
            if row['promptTokens'] > limits['promptTokens']:
                raise CaseFailure('Full prompt exceeds registered context quota; no trimming', row['id'])
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BatchFailure('Registered global time limit reached', row['id'])
            row['inferenceRequestStarted'] = True
            save(out / 'calls.json', calls)
            response = proxy(model.port, 'POST', '/completion', body, min(limits['perCallSeconds'], remaining))
            row.update(response=response, state='returned')
            save(out / 'calls.json', calls)
            if response.get('httpStatus') != 200 or response.get('transportError'):
                raise GroupFailure('Owned model transport/server failed; this model group stops', row['id'])
            value = decode(response['responseUtf8'])
            row.update(content=value.get('content'), tokensGenerated=value.get('tokens_predicted', value.get('timings', {}).get('predicted_n')),
                       stopType=value.get('stop_type'), truncated=value.get('truncated', False))
            if type(row['tokensGenerated']) is not int or not 0 < row['tokensGenerated'] <= limits['generatedTokens'] or type(row['content']) is not str:
                raise GroupFailure('Model response lacks bounded actual generated text/tokens', row['id'], row.get('content'))
            if row['truncated'] or row['stopType'] not in ['eos', 'word']:
                raise CaseFailure('Context/output budget reached; output remains unexecuted', row['id'], row['content'])
            row.update(state='complete', finishedAtUtc=utc())
            return row
        except CaseFailure as failure:
            row.update(failure=type(failure).__name__ + ': ' + str(failure), finishedAtUtc=utc())
            raise
        except BaseException as failure:
            row.update(failure=type(failure).__name__ + ': ' + str(failure), finishedAtUtc=utc())
            raise GroupFailure('Model transport/protocol exception; no restart', row['id'], row.get('content')) from failure
        finally:
            save(out / 'calls.json', calls)
    try:
        assert unchanged() and digest(H / 'REGISTRATION.json') == lock['registrationSha256']
        save(out / 'sdk-precheck.json', verify_sdk())
        log = (out / 'sdk.log').open('wb')
        sdk = Sdk(log)
        bank = Bank(sdk)
        server, thread = serve(bank)
        origin = 'http://127.0.0.1:' + str(server.server_port)
        save(out / 'bank.json', {'origin': origin, 'authenticationTokenSaved': False})
        for model_id in plan['modelOrder']:
            if time.monotonic() >= deadline:
                break
            group = {'model': model_id, 'startedAtUtc': utc()}
            groups.append(group)
            model = None
            with (out / (model_id + '-supervisor.log')).open('wb') as supervisor_log:
                try:
                    model = Model(model_id, 'actual-' + model_id.replace('.', '-'), supervisor_log, min(3700, max(1, deadline - time.monotonic())))
                    group['process'] = model.metadata
                    save(out / 'groups.json', groups)
                    group['properties'] = model.wait_ready(limits['startupSeconds'])
                    for case in [c for c in plan['cases'] if c['model'] == model_id]:
                        if time.monotonic() >= deadline:
                            raise BatchFailure('Registered global time limit reached')
                        statuses[case['id']].update(state='started', atUtc=utc())
                        episodes.append({**case, 'executionComplete': False, 'resetComplete': False})
                        drive(case, bank, origin, complete, checkpoint, max_turns=limits['turnsPerCase'])
                        episode = episodes[-1]
                        statuses[case['id']].update(state='closed' if episode['executionComplete'] else 'partial',
                                                   stopReason=episode.get('stopReason'), finishedAtUtc=utc())
                        save(out / 'statuses.json', statuses)
                        print(json.dumps({'case': case['id'], 'state': statuses[case['id']]['state'],
                                          'calls': len(calls), 'sdkEffects': len(episode.get('sdkRows', [])), 'finished': episode.get('finished')}), flush=True)
                except GroupFailure as failure:
                    group['failure'] = type(failure).__name__ + ': ' + str(failure)
                    if episodes and statuses[episodes[-1]['id']]['state'] == 'started':
                        statuses[episodes[-1]['id']].update(state='partial', stopReason=type(failure).__name__)
                except BatchFailure:
                    raise
                except BaseException as failure:
                    group['failure'] = type(failure).__name__ + ': ' + str(failure)
                    group['traceback'] = traceback.format_exc()
                finally:
                    if model:
                        group.update(healthPolls=model.ready, shutdown=model.close())
                    group['finishedAtUtc'] = utc()
                    save(out / 'groups.json', groups)
        save(out / 'sdk-postcheck.json', verify_sdk())
    except BaseException as failure:
        error = {'error': type(failure).__name__ + ': ' + str(failure), 'traceback': traceback.format_exc()}
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(3)
        if sdk:
            sdk.close()
            save(out / 'sdk-wire.json', sdk.requests)
        if log:
            log.close()
        for status in statuses.values():
            if status['state'] == 'started':
                status['state'] = 'partial'
            if status['state'] == 'unstarted':
                status['reason'] = 'Registered time/resource/group/batch stop; no attempt or hidden retry'
        save(out / 'calls.json', calls)
        save(out / 'episodes.json', episodes)
        save(out / 'statuses.json', statuses)
        summary = {'finishedAtUtc': utc(), 'terminal': True, 'error': error,
                   'plannedCases': len(statuses), 'startedCases': len(episodes),
                   'closedCases': sum(s['state'] == 'closed' for s in statuses.values()),
                   'partialCases': sum(s['state'] == 'partial' for s in statuses.values()),
                   'unstartedCases': sum(s['state'] == 'unstarted' for s in statuses.values()),
                   'evaluationCalls': len(calls), 'inferenceRequestsStarted': sum(c['inferenceRequestStarted'] for c in calls),
                   'returnedResponses': sum('response' in c and c['response'].get('httpStatus') == 200 for c in calls),
                   'sdkMockPayments': sum(len(e.get('sdkRows', [])) for e in episodes),
                   'warmupCalls': 0, 'elapsedSeconds': round(time.monotonic() - start, 3),
                   'sourcesUnchanged': unchanged(), 'sdkWorkerStopped': sdk is None or sdk.process.poll() is not None,
                   'ownedModelShutdownReceipts': all(g.get('shutdown', {}).get('stopped') for g in groups),
                   'newChainOrBankTransactions': 0, 'paidApiCalls': 0}
        save(out / 'execution.json', summary)
        print(json.dumps(summary), flush=True)
    return int(error is not None)

if __name__ == '__main__':
    raise SystemExit(main())
