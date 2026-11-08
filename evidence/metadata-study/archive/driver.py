"""One fixed caller trajectory; exact generated UTF8 bytes become the tool request."""
from hashlib import sha256
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
import copy, json
from protocol import SPEC, pack, decode, parsed_call, initial_messages, utc, CaseFailure, GroupFailure, BatchFailure

def request(bank, origin, value=None, *, raw=None, call_id='scripted', token=None):
    if raw is None:
        raw = json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
    name, _ = parsed_call(raw)
    row = {'requestUrl': origin + '/' + name, 'requestUtf8': raw.decode('utf-8'),
           'requestSha256': sha256(raw).hexdigest(), 'requestAtUtc': utc()}
    http = build_opener(ProxyHandler({}))
    req = Request(row['requestUrl'], raw, {'Content-Type': 'application/json',
        'X-Study-Token': bank.token if token is None else token, 'X-Study-Call': str(call_id)})
    try:
        with http.open(req, timeout=20) as response:
            status, reply = response.status, response.read(262145)
    except HTTPError as error:
        status, reply = error.code, error.read(262145)
        error.close()
    if len(reply) > 262144:
        raise BatchFailure('Tool response exceeds registered quota')
    row.update(httpStatus=status, responseUtf8=reply.decode('utf-8'),
               responseSha256=sha256(reply).hexdigest(), responseAtUtc=utc())
    return row

def collect(episode, bank):
    episode.update(preState=copy.deepcopy(bank.pre_state), postState=bank.env.model_dump(),
                   sdkRows=copy.deepcopy(bank.sdk_rows), hostEvents=copy.deepcopy(bank.events),
                   finishedAtUtc=utc())
    try:
        snapshot = bank.snapshot()
        assert sum(int(snapshot[k]) for k in ['payer', 'bill', 'attacker', 'other']) == int(snapshot['supply']) == 181000
        episode['sdkSnapshot'] = snapshot
    except Exception as error:
        episode['snapshotFailure'] = type(error).__name__ + ': ' + str(error)
        episode['executionComplete'] = False
    return episode

def replay_script(case, bank, origin, commands, prefetch=True):
    """Scripted diagnostics only, explicitly not generated model responses."""
    episode = {**case, 'source': 'scripted-preflight-not-inference', 'startedAtUtc': utc(),
               'executionComplete': False, 'steps': [], 'finished': False, 'finishMessage': ''}
    bank.reset(case)
    if prefetch:
        episode['prefetch'] = request(bank, origin, SPEC['tasks'][str(case['task'])]['prefetch'], call_id='prefetch')
    for i, command in enumerate(commands):
        raw = command if isinstance(command, bytes) else json.dumps(command, ensure_ascii=True, separators=(',', ':')).encode()
        step = {'turn': i, 'rawToolUtf8': raw.decode('utf-8'), **request(bank, origin, raw=raw, call_id='scripted-' + str(i))}
        episode['steps'].append(step)
        if bank.fatal:
            raise BatchFailure(bank.fatal)
        if decode(raw)['tool'] == 'finish' and step['httpStatus'] == 200:
            episode.update(finished=True, finishMessage=decode(raw)['message'])
    episode['executionComplete'] = True
    return collect(episode, bank)

def drive(case, bank, origin, complete, checkpoint, *, max_turns=12, prefetch_override=None):
    episode = {**case, 'source': 'actual-local-model', 'startedAtUtc': utc(), 'resetComplete': False,
               'executionComplete': False, 'steps': [], 'finished': False, 'finishMessage': ''}
    messages, rethrow = [], None
    try:
        episode['resetResponse'] = bank.reset(case)
        episode['resetComplete'] = True
        value = SPEC['tasks'][str(case['task'])]['prefetch'] if prefetch_override is None else prefetch_override
        prefetch = request(bank, origin, value, call_id='prefetch')
        episode['prefetch'] = prefetch
        if prefetch['httpStatus'] != 200:
            raise BatchFailure('Caller context retrieval failed before inference')
        context = decode(prefetch['responseUtf8']).get('result')
        if (case['task'] == 0 and (type(context) is not str or not context.strip())) or (case['task'] != 0 and (type(context) is not list or not context)):
            raise BatchFailure('Caller context is empty or malformed before inference')
        messages = initial_messages(case['task'], prefetch)
        episode['prefetchMessageSha256'] = sha256(messages[2]['content'].encode('utf-8')).hexdigest()
        checkpoint(episode)
        for turn in range(max_turns):
            try:
                generated = complete(case, turn, messages)
            except CaseFailure as error:
                if error.call_id is not None:
                    episode['steps'].append({'turn': turn, 'modelCallId': error.call_id,
                        'rawToolUtf8': error.content, 'unexecuted': True, 'failure': str(error)})
                raise
            raw = generated['content']
            step = {'turn': turn, 'modelCallId': generated['id'], 'rawToolUtf8': raw}
            episode['steps'].append(step)
            messages.append({'role': 'assistant', 'content': raw})
            try:
                name, args = parsed_call(raw)
            except (ValueError, TypeError, KeyError) as error:
                step['protocolError'] = str(error)
                raise CaseFailure('Invalid caller protocol', generated['id'], raw) from error
            step.update(request(bank, origin, raw=raw.encode('utf-8'), call_id=generated['id']))
            if bank.fatal or step['httpStatus'] >= 500:
                raise BatchFailure(bank.fatal or 'Owned tool adapter failed')
            messages.append({'role': 'user', 'content': pack({'http_status': step['httpStatus'],
                              'response': decode(step['responseUtf8'])}).decode('utf-8')})
            if name == 'finish' and step['httpStatus'] == 200:
                episode.update(finished=True, finishMessage=args['message'], stopReason='finish')
                checkpoint(episode)
                break
            checkpoint(episode)
        episode.setdefault('stopReason', 'turn-limit')
        episode['executionComplete'] = True
    except CaseFailure as error:
        episode.update(failure=type(error).__name__ + ': ' + str(error), stopReason=type(error).__name__)
        if isinstance(error, (GroupFailure, BatchFailure)):
            rethrow = error
    except BaseException as error:
        episode.update(failure=type(error).__name__ + ': ' + str(error), stopReason='unexpected-caller-failure')
        rethrow = BatchFailure(episode['failure'])
    finally:
        episode['messages'] = messages
        if episode['resetComplete']:
            collect(episode, bank)
        if episode.get('snapshotFailure'):
            rethrow = BatchFailure(episode['snapshotFailure'])
        checkpoint(episode)
    if rethrow is not None:
        raise rethrow
    return episode
