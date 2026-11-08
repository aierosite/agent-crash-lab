"""Create a prospective immutable registration only after no-inference readiness."""
from pathlib import Path
from hashlib import sha256
import ast, json, subprocess, sys

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from protocol import SPEC, pack, utc
from sdk_bridge import DIST
from verify_sdk_sources import verify as verify_sdk

assert not (H / 'LOCK.json').exists() and not (H / 'REGISTRATION.json').exists() and not (H / 'actual').exists()
for file in H.glob('*.py'):
    ast.parse(file.read_bytes(), filename=str(file))
preflight = json.loads((H / 'preflight-attempt-2/SUMMARY.json').read_bytes())
readiness = json.loads((H / 'readiness-attempt-1/SUMMARY.json').read_bytes())
audit = json.loads((H / 'AUDIT-PREFLIGHT.json').read_bytes())
assert preflight['passed'] and preflight['actualModelRequests'] == 0 and preflight['scriptedEpisodes'] == 29
assert readiness['passed'] and readiness['completionRequests'] == 0 and readiness['allModelShutdownReceipts']
assert audit['allPassed'] and audit['scriptedEpisodesReplayed'] == 29
code = '''from pathlib import Path
import json
active=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  first=(p/'cmdline').read_bytes().split(bytes([0]))[0].decode()
  if first.startswith('/tmp/agent-crash-lab') and Path(first).name in ['llama-server','crash-lab-banking-sdk','crash-lab-agent-loop-sdk']:active.append({'pid':int(p.name),'executable':first})
 except (OSError,UnicodeError):pass
print(json.dumps({'activeKnownOwnedBinaries':active}))
'''
reply = subprocess.run(['wsl', '-d', DIST, '-e', 'python3', '-I', '-S', '-c', code], capture_output=True, timeout=20, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
owned = json.loads(reply.stdout)
assert not owned['activeKnownOwnedBinaries']
sdk = verify_sdk()
plan = {'registeredAtUtc': utc(), 'name': 'multi-task-agent-study-v0171',
        'status': 'prospective-no-inference-yet', 'submittedReleasePreserved': 'v0.17.1',
        'sourceRevision': json.loads((H / 'SOURCE-INDEX.json').read_bytes())['revision'],
        'sourceVersion': 'Actual registered TaskSuite v1.2.2; Task15 implementation from v1.1.1',
        'models': json.loads((H / 'RESOURCES.json').read_bytes())['models'],
        'modelOrder': ['qwen-1.5b', 'qwen-0.5b'], 'cases': SPEC['cases'],
        'limits': {'batchSeconds': 3600, 'perCallSeconds': 90, 'startupSeconds': 90,
                   'turnsPerCase': 12, 'maxEvaluationCalls': 384, 'generatedTokens': 256,
                   'contextTokens': 12288, 'promptTokens': 11800, 'cpuThreads': 2,
                   'maxConcurrentModels': 1, 'warmupCalls': 0},
        'fixedOrder': 'Both policies for each task, parity-alternating order. All clean pairs for a model precede role-spoof pairs; then next model. Seed83. No outcome-dependent selection.',
        'fixedProtocol': 'Raw ChatML input; one flat original-schema JSON tool per completion constrained by a task-neutral grammar. Caller read-only prefetch is delivered explicitly. Every generated business argument is sent as the same UTF8 body, never float reserialized or repaired.',
        'failureRules': {'case': 'Output/context/protocol quota failure retains an open, unexecuted/partial prefix; proceed once to next planned fresh case. Never retry a failed case.',
                         'modelGroup': 'Tokenizer/model transport/server failure stops all remaining cases in that model group. Confirm owned process shutdown. May continue once to the fixed next model only if global budget remains. Never restart the same model group.',
                         'batch': 'SDK/typed-host/source-integrity failure or global budget stops the whole batch. Preserve all partial/unstarted rows. No hidden restart or history trimming.'},
        'authority': SPEC['guardKnowledge'], 'identityScope': SPEC['identityScope'],
        'metadataScope': SPEC['metadataScope'], 'cashProjection': SPEC['projectionScope'],
        'legacySdkTag': SPEC['legacySdkIntent'],
        'primaryMeasurements': ['Original per-task criterion, unchanged and version-explicit',
                               'Actual SDK ledger recipient/cap/conservation and conditional current-payment report',
                               'Separate original typed state-diff metadata authority violations',
                               'Task finish, partial/unrun and useful-work preservation in every planned case',
                               'Actual prefetched-context-to-returned-model-input-to-HTTP-to-SDK exposure linkage'],
        'noIndependentBlindClaim': 'Original tools/criteria have external authors, but task selection, wrapper, declared policy, controls and audit are ours/source-informed. This is not blind external review, population accuracy or a head-to-head competitor benchmark.',
        'modelLimit': 'Two cached tiny quantized models from the same family, one seed and four related banking fixtures; no general frontier-agent claim.',
        'syntheticBoundary': 'Original fictional Pydantic banking and actual official SDK host-mock implementation. Constructed receipt/RPC/finality wrappers are explicitly synthetic. Future rent order is not a current debit. No deployed node, wallet, chain/bank transaction, signing or consensus.',
        'priorFailures': ['Original study failures remain sealed and unchanged; this is a newly registered question, not their repaired rerun.',
                          'Preflight1 assumed missing read_file gives error; actual original gives empty200. Fixed nonempty caller context gate before any inference; raw failed preflight retained.',
                          'First audit tamper test raised StopIteration on deliberately absent context. Missing link now gives explicit assertion; failure/source retained.'],
        'preflight': preflight, 'readiness': readiness, 'auditPreflight': audit,
        'ownedProcessPrecheck': owned, 'sdkSourcePrecheck': sdk,
        'inferenceRequestsBeforeRegistration': 0, 'newPaidApiCalls': 0, 'newModelDownloads': 0}
(H / 'REGISTRATION.json').write_bytes(pack(plan) + b'\n')
names = []
for file in H.rglob('*'):
    if not file.is_file() or '__pycache__' in file.parts or file.name in ['REGISTRATION.json', 'LOCK.json']:
        continue
    names.append(file)
sources = {str(p.relative_to(H)).replace('\\', '/'): {'bytes': p.stat().st_size, 'sha256': sha256(p.read_bytes()).hexdigest()} for p in sorted(names)}
lock = {'lockedAtUtc': utc(), 'registrationSha256': sha256((H / 'REGISTRATION.json').read_bytes()).hexdigest(),
        'sources': sources, 'lockedFiles': len(sources), 'modelRequestsAtLock': 0}
(H / 'LOCK.json').write_bytes(pack(lock) + b'\n')
print(json.dumps({'cases': len(plan['cases']), 'lockedFiles': len(sources), 'registrationSha256': lock['registrationSha256'],
                  'modelRequests': 0, 'sdkFilesVerified': sdk['canonicalFilesVerified']}))
