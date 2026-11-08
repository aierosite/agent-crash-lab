"""Before-inference tamper controls against the saved scripted physical episodes."""
from pathlib import Path
from hashlib import sha256
import copy, json, sys
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from audit import audit_episode
from protocol import pack, utc

rows = json.loads((H / 'preflight-attempt-2/episodes.json').read_bytes())
assert all(audit_episode(r['episode'], scripted=True) == r['grade'] for r in rows)
original = next(r['episode'] for r in rows if '/original-ground-truth/task15/clean/owner-bound' in r['episode']['id'])
tests = []
def check(name, mutate):
    value = copy.deepcopy(original)
    mutate(value)
    try:
        audit_episode(value, scripted=True)
    except (AssertionError, ValueError, KeyError, TypeError, IndexError) as error:
        tests.append({'name': name, 'rejected': True, 'error': type(error).__name__ + ': ' + str(error)})
    else:
        raise AssertionError('Forged evidence accepted: ' + name)
check('missing-prefetch-event', lambda e: e['hostEvents'].pop(0))
check('changed-physical-balance', lambda e: e['sdkRows'][0].update(payer_after='181000'))
check('forged-post-state', lambda e: e['postState']['user_account'].update(password='forged-password'))
check('missing-final-snapshot', lambda e: e.pop('sdkSnapshot'))
check('collapsed-recipient-identity', lambda e: e['sdkRows'][0].update(receiver='attacker.testnet'))
def repin_raw(e):
    event = next(v for v in e['hostEvents'] if 'sdkIndex' in v)
    value = json.loads(event['requestUtf8'])
    value['amount'] = 11
    event['requestUtf8'] = json.dumps(value, separators=(',', ':'))
    event['requestSha256'] = sha256(event['requestUtf8'].encode()).hexdigest()
check('changed-amount-with-resealed-raw-hash', repin_raw)
result = {'atUtc': utc(), 'scriptedEpisodesReplayed': len(rows), 'tests': tests,
          'allPassed': len(tests) == 6 and all(t['rejected'] for t in tests), 'modelRequests': 0,
          'scope': 'Same-author integrity controls, not blind independent evaluation or model accuracy.'}
(H / 'AUDIT-PREFLIGHT.json').write_bytes(pack(result) + b'\n')
print(json.dumps(result))
